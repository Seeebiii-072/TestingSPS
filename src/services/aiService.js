import axios from 'axios';
import { AI_URL } from '../config/constants.js';

const aiApi = axios.create({
  baseURL: AI_URL,
});

export async function enhanceDescription(subject, description) {
  const response = await aiApi.post('/api/enhance-description', { subject, description });
  return {
    ...response.data,
    enhanced_description: response.data.enhanced_description?.replace(/\s+/g, ' ').trim(),
  };
}

const aiService = {
  enhanceDescription,
};

export default aiService;
