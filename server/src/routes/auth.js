// Authentication routes
import { Router } from 'express';
import bcrypt from 'bcryptjs';
import rateLimit from 'express-rate-limit';
import path from 'path';
import { fileURLToPath } from 'url';
import { config } from '../config.js';
import { requireGuest } from '../middleware/auth.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const VIEWS_DIR = path.join(__dirname, '../../views');

const router = Router();

// In-memory user store (replace with database in production)
// Default admin user - password should be changed immediately
const users = [
  {
    id: 1,
    username: 'admin',
    passwordHash: bcrypt.hashSync('admin123', 10),
    role: 'admin',
  },
];

// Login rate limiter
const loginLimiter = rateLimit({
  windowMs: config.rateLimit.login.windowMs,
  limit: config.rateLimit.login.limit,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { error: 'Too many login attempts, please try again later.' },
});

router.get('/', requireGuest, (req, res) => {
  res.sendFile('login.html', { root: VIEWS_DIR });
});

router.post('/', loginLimiter, async (req, res) => {
  try {
    // Login is meaningless while the panel is public.
    if (!config.auth.enabled) {
      return res.status(400).json({ error: 'Authentication is disabled' });
    }

    const { username, password } = req.body;

    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const user = users.find(u => u.username === username);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const validPassword = await bcrypt.compare(password, user.passwordHash);
    if (!validPassword) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    req.session.authenticated = true;
    req.session.userId = user.id;
    req.session.username = user.username;
    req.session.role = user.role;

    res.json({ success: true, redirect: '/' });
  } catch (error) {
    console.error('[ERROR] Login error:', error.message);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.post('/logout', (req, res) => {
  req.session.destroy((err) => {
    if (err) {
      return res.status(500).json({ error: 'Failed to logout' });
    }
    res.json({ success: true });
  });
});

export default router;
