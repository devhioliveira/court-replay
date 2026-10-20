// Error handling middleware
export function errorHandler(err, req, res, next) {
  console.error('[ERROR]', err.message);

  // Don't leak stack traces in production
  const isDev = process.env.NODE_ENV === 'development';

  if (err.type === 'entity.too.large') {
    return res.status(413).json({ error: 'Request body too large' });
  }

  if (err.type === 'entity.parse.failed') {
    return res.status(400).json({ error: 'Invalid JSON body' });
  }

  res.status(err.status || 500).json({
    error: isDev ? err.message : 'Internal server error',
    ...(isDev && { stack: err.stack }),
  });
}

export function notFound(req, res) {
  res.status(404).json({ error: 'Not found' });
}
