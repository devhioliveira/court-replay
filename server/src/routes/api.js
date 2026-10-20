// API routes
import { Router } from 'express';
import rateLimit from 'express-rate-limit';
import { config } from '../config.js';
import { requireAuth } from '../middleware/auth.js';
import { notebookAgent } from '../services/notebookAgent.js';

const router = Router();

// All API routes require authentication
router.use(requireAuth);

// Health check
router.get('/health', async (req, res) => {
  const agentHealth = await notebookAgent.healthCheck();
  res.json({
    status: 'ok',
    server: 'online',
    agent: agentHealth.status === 'ok' ? 'online' : 'offline',
    // Lets the frontend hide the logout button when there is no login.
    authEnabled: config.auth.enabled,
    timestamp: new Date().toISOString(),
  });
});

// Status
router.get('/status', async (req, res) => {
  try {
    const agentStatus = await notebookAgent.getStatus();
    res.json({
      camera: { name: config.camera.name, ip: config.camera.ip },
      notebook: agentStatus,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.json({
      camera: { name: config.camera.name, ip: config.camera.ip },
      notebook: { state: 'OFFLINE', error: error.message },
      timestamp: new Date().toISOString(),
    });
  }
});

// List clips
router.get('/clips', async (req, res) => {
  try {
    const { start, end } = req.query;
    const result = await notebookAgent.getClips(start, end);
    res.json(result);
  } catch (error) {
    res.status(502).json({ error: 'Failed to fetch clips from agent' });
  }
});

// Get single clip info
router.get('/clips/:id', async (req, res) => {
  try {
    const clipId = req.params.id;

    // Validate clip ID format (prevent path traversal)
    if (!/^[a-zA-Z0-9_-]+$/.test(clipId)) {
      return res.status(400).json({ error: 'Invalid clip ID' });
    }

    const clip = await notebookAgent.getClip(clipId);
    res.json(clip);
  } catch (error) {
    if (error.response && error.response.status === 404) {
      return res.status(404).json({ error: 'Clip not found' });
    }
    res.status(502).json({ error: 'Failed to fetch clip from agent' });
  }
});

// Download clip (streaming)
router.get('/clips/:id/download', async (req, res) => {
  try {
    const clipId = req.params.id;

    // Validate clip ID format
    if (!/^[a-zA-Z0-9_-]+$/.test(clipId)) {
      return res.status(400).json({ error: 'Invalid clip ID' });
    }

    const rangeHeader = req.headers.range || null;
    const response = await notebookAgent.downloadClip(clipId, rangeHeader);

    // Forward headers
    if (response.headers['content-type']) {
      res.setHeader('Content-Type', response.headers['content-type']);
    }
    if (response.headers['content-length']) {
      res.setHeader('Content-Length', response.headers['content-length']);
    }
    if (response.headers['content-disposition']) {
      res.setHeader('Content-Disposition', response.headers['content-disposition']);
    }
    if (response.headers['content-range']) {
      res.setHeader('Content-Range', response.headers['content-range']);
    }
    if (response.headers['accept-ranges']) {
      res.setHeader('Accept-Ranges', response.headers['accept-ranges']);
    }

    res.status(response.status);
    response.data.pipe(res);
  } catch (error) {
    if (error.response && error.response.status === 404) {
      return res.status(404).json({ error: 'Clip not found' });
    }
    res.status(502).json({ error: 'Failed to download clip from agent' });
  }
});

// Trigger clip creation
router.post('/clips/trigger', async (req, res) => {
  try {
    const result = await notebookAgent.triggerClip();
    res.json(result);
  } catch (error) {
    res.status(502).json({ error: 'Failed to trigger clip creation' });
  }
});

// Delete clip
// Intentionally NOT exposed: this panel is for end users, who must not be able
// to delete clips. Deletion still exists on the agent's internal API (used by
// the midnight cleanup). To allow it from the panel, re-add a route here guarded
// by an admin check - never expose it on a public panel.
// router.delete('/clips/:id', ...)

export default router;
