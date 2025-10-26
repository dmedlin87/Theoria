import AudioUploader from '../../components/AudioUploader';
import { useState } from 'react';

type DocumentType = {
  id: string;
  title: string;
};

export default function IngestPage() {
  const [uploadResult, setUploadResult] = useState<DocumentType | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleUploadSuccess = (document: DocumentType) => {
    setUploadResult(document);
    setError(null);
  };

  const handleUploadError = (err: string) => {
    setError(err);
    setUploadResult(null);
  };

  return (
    <div className="max-w-3xl mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Ingest Audio Content</h1>
      
      <AudioUploader 
        onUploadSuccess={handleUploadSuccess}
        onUploadError={handleUploadError}
      />
      
      {error && (
        <div className="mt-6 p-4 bg-red-100 text-red-700 rounded">
          <p>{error}</p>
        </div>
      )}
      
      {uploadResult && (
        <div className="mt-6 p-4 bg-green-50 rounded">
          <h2 className="text-lg font-semibold mb-2">Ingestion Successful!</h2>
          <p>Document ID: {uploadResult.id}</p>
          <p className="mt-2">
            <a 
              href={`/documents/${uploadResult.id}`} 
              className="text-blue-600 hover:underline"
            >
              View document
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
