import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import FileUploadForm from "../../app/upload/components/FileUploadForm";

describe("FileUploadForm", () => {
  it("streams the selected file to the upload endpoint and resets the form", async () => {
    const uploads: { file: File; frontmatter: string }[] = [];
    const resetSpy = vi.spyOn(HTMLFormElement.prototype, "reset");
    const handleUpload = vi.fn(async (file: File, frontmatter: string) => {
      uploads.push({ file, frontmatter });
    });

    const user = userEvent.setup();

    render(<FileUploadForm onUpload={handleUpload} isUploading={false} />);

    const fileControl = screen.getByLabelText(/Source file/i, { selector: "input" });
    const frontmatterInput = screen.getByLabelText(/Frontmatter/i, { selector: "textarea" });
    const submitButton = screen.getByRole("button", { name: /Upload file/i });

    const file = new File(["sermon"], "sermon.txt", { type: "text/plain" });

    await user.upload(fileControl, file);
    expect(fileControl.files?.item(0)?.name).toBe("sermon.txt");
    fireEvent.change(frontmatterInput, {
      target: { value: JSON.stringify({ collection: "Gospels" }) },
    });

    const form = submitButton.closest("form");
    if (!form) {
      throw new Error("File upload form not found");
    }
    fireEvent.submit(form);

    await waitFor(() => expect(handleUpload).toHaveBeenCalledTimes(1));
    expect(uploads[0]).toMatchObject({
      frontmatter: '{"collection":"Gospels"}',
    });
    expect(uploads[0].file.name).toBe("sermon.txt");
    expect(frontmatterInput.value).toBe("");
    expect(resetSpy).toHaveBeenCalled();
    resetSpy.mockRestore();
  });
});
