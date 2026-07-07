import { useState, useEffect, useCallback } from 'react';
import kbService from '../../services/kbService.js';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import Button from '../../components/common/Button';

export default function KnowledgeBase() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ filename: '', content: '' });
  const [selectedFile, setSelectedFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [deletingFile, setDeletingFile] = useState(null);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const docs = await kbService.listDocuments();
      setDocuments(docs);
    } catch {
      setError('Could not load documents. Make sure the AI service is running on port 8001.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setFormError('');
    setSubmitting(true);
    try {
      await kbService.createDocument(form.filename.trim(), form.content.trim());
      setShowForm(false);
      setForm({ filename: '', content: '' });
      setSelectedFile(null);
      await loadDocuments();
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create document. Check that the filename ends in .txt and does not already exist.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Delete "${filename}" from the knowledge base? This will remove it from AI chat responses.`)) return;
    setDeletingFile(filename);
    try {
      await kbService.deleteDocument(filename);
      await loadDocuments();
    } catch {
      alert('Failed to delete document.');
    } finally {
      setDeletingFile(null);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.txt')) {
      setFormError('Only .txt files are supported.');
      return;
    }
    setSelectedFile(file);
    // Auto-set the filename from the uploaded file
    setForm((f) => ({ ...f, filename: file.name }));
    // Read the file content
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result || '';
      setForm((f) => ({ ...f, content }));
    };
    reader.onerror = () => {
      setFormError('Failed to read the selected file. Please try again.');
    };
    reader.readAsText(file);
  };

  const updateField = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const cancelForm = () => {
    setShowForm(false);
    setForm({ filename: '', content: '' });
    setSelectedFile(null);
    setFormError('');
  };

  return (
    <section className="page admin-management-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">System administration</p>
          <h1>Knowledge Base</h1>
          <p>Manage support documents indexed for SecureDesk AI chat. Changes take effect immediately.</p>
        </div>
        {!showForm && (
          <Button onClick={() => setShowForm(true)}>Add Document</Button>
        )}
      </div>

          {showForm && (
        <Card className="admin-management-card" title="Add KB document" subtitle="Only .txt files are supported. Content is indexed immediately into the AI vector store.">
          <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', padding: '0.5rem 0' }}>
            <label>
              Select .txt file from your computer
              <input
                type="file"
                accept=".txt"
                onChange={handleFileSelect}
                style={{ marginTop: '0.25rem' }}
              />
              {selectedFile && (
                <span style={{ display: 'block', fontSize: '0.85rem', color: 'var(--color-text-subtle)', marginTop: '0.25rem' }}>
                  Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              )}
            </label>
            <label>
              Filename (auto-filled from file, can be edited)
              <input
                name="filename"
                required
                placeholder="e.g. VPN Setup Guide.txt"
                value={form.filename}
                onChange={updateField}
              />
            </label>
            <label>
              Document content (loaded from file, editable)
              <textarea
                name="content"
                required
                rows={10}
                placeholder="Select a .txt file above to load its content…"
                value={form.content}
                onChange={updateField}
                style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: '0.85rem' }}
              />
            </label>
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Uploading…' : 'Upload Document'}
              </Button>
              <Button variant="outline" type="button" onClick={cancelForm}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card
        className="admin-management-card"
        title="Indexed documents"
        subtitle="Documents available to SecureDesk AI for grounded chat responses."
        actions={<Badge tone="blue">{documents.length} documents</Badge>}
      >
        {loading && <p style={{ padding: '1rem', color: 'var(--color-text-subtle)' }}>Loading documents…</p>}
        {error && <p className="form-error" role="alert" style={{ padding: '1rem' }}>{error}</p>}
        {!loading && !error && (
          <div className="admin-management-table-wrap">
            <table className="admin-management-table">
              <caption className="visually-hidden">Knowledge base documents</caption>
              <thead>
                <tr>
                  <th scope="col">Filename</th>
                  <th scope="col">Chunks</th>
                  <th scope="col">Indexed</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                {documents.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--color-text-subtle)' }}>
                      No documents indexed yet. Use the Add Document button above.
                    </td>
                  </tr>
                )}
                {documents.map((doc) => (
                  <tr key={doc.filename}>
                    <td>{doc.filename}</td>
                    <td>{doc.chunk_count}</td>
                    <td>{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}</td>
                    <td>
                      <Button
                        variant="outline"
                        onClick={() => handleDelete(doc.filename)}
                        disabled={deletingFile === doc.filename}
                      >
                        {deletingFile === doc.filename ? 'Deleting…' : 'Delete'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </section>
  );
}