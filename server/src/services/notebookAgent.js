// HMAC authentication service for Node.js <-> Python Agent communication
import crypto from 'crypto';
import axios from 'axios';
import { config } from '../config.js';

class NotebookAgentService {
  constructor() {
    this.baseUrl = `http://${config.notebookAgent.host}:${config.notebookAgent.port}`;
    this.timeout = config.notebookAgent.timeout;
    this.sharedSecret = config.notebookAgent.sharedSecret;
  }

  _generateSignature(method, path, body = '') {
    const timestamp = Date.now().toString();
    const nonce = crypto.randomBytes(16).toString('hex');
    // Must match the Python side exactly: method|path+query|timestamp|nonce|hex(body)
    const payload = `${method}|${path}|${timestamp}|${nonce}|${Buffer.from(body).toString('hex')}`;
    const signature = crypto
      .createHmac(config.security.hmacAlgorithm, this.sharedSecret)
      .update(payload)
      .digest('hex');
    return { signature, timestamp, nonce };
  }

  _getHeaders(method, path, body = '') {
    const { signature, timestamp, nonce } = this._generateSignature(method, path, body);
    return {
      'X-Auth-Signature': signature,
      'X-Auth-Timestamp': timestamp,
      'X-Auth-Nonce': nonce,
      'Content-Type': 'application/json',
    };
  }

  async healthCheck() {
    try {
      const response = await axios.get(`${this.baseUrl}/health`, {
        headers: this._getHeaders('GET', '/health'),
        timeout: 5000,
      });
      return response.data;
    } catch (error) {
      return { status: 'offline', error: error.message };
    }
  }

  async getStatus() {
    const response = await axios.get(`${this.baseUrl}/api/internal/status`, {
      headers: this._getHeaders('GET', '/api/internal/status'),
      timeout: this.timeout,
    });
    return response.data;
  }

  async getClips(startTime, endTime) {
    const params = new URLSearchParams();
    if (startTime) params.append('start', startTime);
    if (endTime) params.append('end', endTime);
    const queryString = params.toString();
    const path = `/api/internal/clips${queryString ? '?' + queryString : ''}`;

    const response = await axios.get(`${this.baseUrl}${path}`, {
      headers: this._getHeaders('GET', path),
      timeout: this.timeout,
    });
    return response.data;
  }

  async getClip(clipId) {
    const path = `/api/internal/clips/${clipId}`;
    const response = await axios.get(`${this.baseUrl}${path}`, {
      headers: this._getHeaders('GET', path),
      timeout: this.timeout,
    });
    return response.data;
  }

  async deleteClip(clipId) {
    const path = `/api/internal/clips/${clipId}/delete`;
    const body = '{}';
    const response = await axios.post(`${this.baseUrl}${path}`, {}, {
      headers: this._getHeaders('POST', path, body),
      timeout: this.timeout,
    });
    return response.data;
  }

  async triggerClip() {
    const path = '/api/internal/trigger';
    const body = '{}';
    const response = await axios.post(`${this.baseUrl}${path}`, {}, {
      headers: this._getHeaders('POST', path, body),
      timeout: this.timeout,
    });
    return response.data;
  }

  async downloadClip(clipId, rangeHeader = null) {
    const path = `/api/internal/clips/${clipId}/download`;
    const headers = this._getHeaders('GET', path);
    if (rangeHeader) {
      headers['Range'] = rangeHeader;
    }

    const response = await axios.get(`${this.baseUrl}${path}`, {
      headers,
      responseType: 'stream',
      timeout: this.timeout,
    });
    return response;
  }
}

export const notebookAgent = new NotebookAgentService();
