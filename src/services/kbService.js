import axios from 'axios';
import { AI_URL } from '../config/constants.js';

const aiApi = axios.create({ baseURL: AI_URL });

async function listDocuments() {
  const response = await aiApi.get('/kb/documents');
  return response.data;
}

async function createDocument(filename, content) {
  const response = await aiApi.post('/kb/documents', { filename, content });
  return response.data;
}

async function updateDocument(filename, content) {
  const response = await aiApi.put(`/kb/documents/${encodeURIComponent(filename)}`, { content });
  return response.data;
}

async function deleteDocument(filename) {
  const response = await aiApi.delete(`/kb/documents/${encodeURIComponent(filename)}`);
  return response.data;
}

const kbService = { 
  listDocuments, 
  createDocument, 
  updateDocument, 
  deleteDocument 
};

export default kbService;