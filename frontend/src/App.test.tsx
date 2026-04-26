/**
 * Smoke tests for pure helpers — avoids importing App.tsx (and its
 * react-router-dom ESM imports that CRA's Jest can't transform without
 * extra config).
 */
import { saveVaultKey, getVaultKey, removeVaultKey, getApiBase, getFileUrl } from './services/api';

beforeEach(() => {
  localStorage.clear();
});

test('vault api keys round-trip through localStorage', () => {
  saveVaultKey('alpha', 'sk-embed-test-123');
  expect(getVaultKey('alpha')).toBe('sk-embed-test-123');
  removeVaultKey('alpha');
  expect(getVaultKey('alpha')).toBe('');
});

test('getApiBase returns a non-empty URL', () => {
  expect(getApiBase()).toMatch(/^https?:\/\//);
});

test('getFileUrl prefixes relative paths with API base', () => {
  const url = getFileUrl('/uploads/foo/bar.png');
  expect(url).toMatch(/uploads\/foo\/bar\.png$/);
});
