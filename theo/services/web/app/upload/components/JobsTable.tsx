"use client";

interface JobStatus {
  id: string;
  document_id?: string | null;
  job_type: string;
  status: string;
  task_id?: string | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

interface JobsTableProps {
  jobs: JobStatus[];
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

export default function JobsTable({ jobs }: JobsTableProps): JSX.Element {
  if (jobs.length === 0) {
    return (
      <div className="alert alert-info">
        <div className="alert__message">No jobs queued yet.</div>
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="jobs-table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Status</th>
            <th>Document</th>
            <th>Updated</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>{job.job_type}</td>
              <td>
                <span className={`badge badge-${job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "secondary"}`}>
                  {job.status}
                </span>
              </td>
              <td className="text-sm text-muted">{job.document_id ?? "—"}</td>
              <td className="text-sm text-muted">{formatTimestamp(job.updated_at)}</td>
              <td className="text-sm" style={{ color: job.error ? "var(--color-danger)" : "var(--color-text-muted)" }}>
                {job.error || ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <style jsx>{`
        .jobs-table {
          width: 100%;
          border-collapse: collapse;
          min-width: 640px;
        }

        .jobs-table th {
          text-align: left;
          padding: var(--space-2);
          border-bottom: 1.5px solid var(--color-border-subtle);
          font-weight: 600;
          color: var(--color-text-primary);
          background: var(--color-surface-muted);
        }

        .jobs-table td {
          padding: var(--space-2);
          border-bottom: 1px solid var(--color-border-subtle);
        }

        .jobs-table tbody tr:hover {
          background: var(--color-surface-muted);
        }
      `}</style>
    </div>
  );
}
