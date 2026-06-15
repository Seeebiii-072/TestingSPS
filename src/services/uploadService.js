import { uploadFile as uploadTicketFile } from './ticketService.js';

export function uploadFile(ticketId, file) {
  return uploadTicketFile(ticketId, file);
}

const uploadService = {
  uploadFile,
};

export default uploadService;
