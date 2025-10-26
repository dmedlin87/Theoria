import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';

type DocumentType = {
  id: string;
  title: string;
  // Add other document properties as needed
};

type AudioUploaderProps = {
  onUploadSuccess: (document: DocumentType) => void;
  onUploadError: (error: string) => void;
};

export default function AudioUploader({ 
  onUploadSuccess, 
  onUploadError 
}: AudioUploaderProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [sourceType, setSourceType] = useState('sermon');
  const [notebookLmMetadata, setNotebookLmMetadata] = useState('');
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'audio/*': ['.mp3', '.wav'],
      'video/*': ['.mp4']
    },
    maxFiles: 1,
    onDrop: acceptedFiles => {
      handleUpload(acceptedFiles[0]);
    },
  });

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    
    const formData = new FormData();
    formData.append('audio', file);
    formData.append('source_type', sourceType);
    
    if (notebookLmMetadata) {
      formData.append('notebooklm_metadata', notebookLmMetadata);
    }
    
    try {
      const response = await fetch('/api/ingest/audio', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
      }
      
      const result = await response.json();
      onUploadSuccess(result);
    } catch (error) {
      onUploadError(error.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="p-6 border rounded-lg">
      <div 
        {...getRootProps()} 
        className={`p-8 border-2 border-dashed rounded-md text-center ${
          isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
        }`}
      >
        <input {...getInputProps()} />
        <p>{isDragActive ? 'Drop audio here' : 'Drag audio file or click to select'}</p>
        <p className="text-sm text-gray-500">Supports MP3, WAV, MP4 files</p>
      </div>
      
      <div className="mt-4">
        <label className="block mb-2 font-medium">Source Type</label>
        <select 
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          className="w-full p-2 border rounded"
        >
          <option value="sermon">Sermon</option>
          <option value="podcast">Podcast</option>
          <option value="ai_generated">AI-Generated</option>
          <option value="lecture">Lecture</option>
          <option value="other">Other</option>
        </select>
      </div>
      
      <div className="mt-4">
        <label className="block mb-2 font-medium">
          NotebookLM Metadata (JSON)
          <span className="text-gray-500 font-normal"> - Optional</span>
        </label>
        <textarea 
          value={notebookLmMetadata}
          onChange={(e) => setNotebookLmMetadata(e.target.value)}
          placeholder={`{"agents": ["Theologian", "Historian"], "source_research": ["doc:123"]}`}
          className="w-full p-2 border rounded h-24"
        />
      </div>
      
      {isUploading && (
        <div className="mt-4 text-center">
          <p>Processing audio... This may take several minutes</p>
          <progress className="w-full" />
        </div>
      )}
    </div>
  );
}
