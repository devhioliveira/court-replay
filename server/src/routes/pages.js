// Page routes
import { Router } from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import { requireAuth } from '../middleware/auth.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Absolute path so the server works regardless of the current working directory.
const VIEWS_DIR = path.join(__dirname, '../../views');

const router = Router();

router.get('/', requireAuth, (req, res) => {
  res.sendFile('index.html', { root: VIEWS_DIR });
});

export default router;
