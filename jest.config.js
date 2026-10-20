export default {
  testEnvironment: 'node',
  coverageDirectory: 'coverage',
  collectCoverageFrom: [
    'server/src/**/*.js',
    '!server/src/index.js',
  ],
  testMatch: [
    '**/tests/**/*.test.js',
  ],
};
