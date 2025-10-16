import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CitationExport from '../../app/components/CitationExport';

describe('CitationExport', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('previews citations using the selected style', async () => {
    const mockResponse = {
      ok: true,
      json: vi.fn().mockResolvedValue({
        manifest: { export_id: 'fixture' },
        records: [{ citation: 'Example SBL citation' }],
      }),
      headers: new Headers(),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse as unknown as Response) as unknown as typeof fetch;

    render(<CitationExport defaultStyle="sbl" />);

    fireEvent.change(screen.getByLabelText('Document identifiers'), {
      target: { value: 'doc-1' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Preview citations' }));

    await screen.findByText('Example SBL citation');

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/export/citations',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const body = JSON.parse((globalThis.fetch as vi.Mock).mock.calls[0][1].body as string);
    expect(body.style).toBe('sbl');
    expect(body.document_ids).toEqual(['doc-1']);
  });

  it('triggers a download and shows success feedback', async () => {
    const blobSpy = vi.fn().mockResolvedValue(new Blob(['data'], { type: 'text/plain' }));
    const response = {
      ok: true,
      blob: blobSpy,
      headers: new Headers({ 'Content-Disposition': 'attachment; filename="export.md"' }),
    } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(response) as unknown as typeof fetch;

    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;
    const createObjectUrlSpy = vi.fn().mockReturnValue('blob:mock');
    const revokeObjectUrlSpy = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', {
      value: createObjectUrlSpy,
      configurable: true,
      writable: true,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      value: revokeObjectUrlSpy,
      configurable: true,
      writable: true,
    });
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    render(<CitationExport />);

    fireEvent.change(screen.getByLabelText('Document identifiers'), {
      target: { value: 'doc-1' },
    });

    fireEvent.click(screen.getByRole('button', { name: /Download/ }));

    await screen.findByText('Downloaded export.md');

    expect(blobSpy).toHaveBeenCalled();
    expect(createObjectUrlSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith('blob:mock');
    expect(clickSpy).toHaveBeenCalled();

    if (originalCreateObjectURL) {
      Object.defineProperty(URL, 'createObjectURL', {
        value: originalCreateObjectURL,
        configurable: true,
        writable: true,
      });
    } else {
      delete (URL as unknown as { createObjectURL?: typeof URL.createObjectURL }).createObjectURL;
    }
    if (originalRevokeObjectURL) {
      Object.defineProperty(URL, 'revokeObjectURL', {
        value: originalRevokeObjectURL,
        configurable: true,
        writable: true,
      });
    } else {
      delete (URL as unknown as { revokeObjectURL?: typeof URL.revokeObjectURL }).revokeObjectURL;
    }
  });

  it('surfaces API errors when preview fails', async () => {
    const response = {
      ok: false,
      text: vi.fn().mockResolvedValue('Failure!'),
    } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(response) as unknown as typeof fetch;

    render(<CitationExport />);

    fireEvent.change(screen.getByLabelText('Document identifiers'), {
      target: { value: 'doc-1' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Preview citations' }));

    await screen.findByText('Failure!');
  });

  it('invokes the Zotero hook when preview data includes items', async () => {
    const zoteroHandler = vi.fn();
    const mockResponse = {
      ok: true,
      json: vi.fn().mockResolvedValue({
        manifest: { export_id: 'fixture' },
        records: [],
        manager_payload: { zotero: { items: [{ id: 'doc-1' }] } },
      }),
      headers: new Headers(),
    };
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse as unknown as Response) as unknown as typeof fetch;

    render(<CitationExport onZoteroItems={zoteroHandler} />);

    fireEvent.change(screen.getByLabelText('Document identifiers'), {
      target: { value: 'doc-1' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Preview citations' }));

    await waitFor(() => {
      expect(zoteroHandler).toHaveBeenCalledWith([{ id: 'doc-1' }]);
    });
  });
});
