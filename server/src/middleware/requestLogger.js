// Request logging middleware
export function requestLogger(req, res, next) {
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    const logEntry = {
      method: req.method,
      path: req.originalUrl,
      status: res.statusCode,
      duration: `${duration}ms`,
      ip: req.ip,
      userAgent: req.get('user-agent'),
    };

    if (res.statusCode >= 400) {
      console.log('[WARN]', JSON.stringify(logEntry));
    } else {
      console.log('[INFO]', JSON.stringify(logEntry));
    }
  });

  next();
}
