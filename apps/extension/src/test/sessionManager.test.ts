import * as assert from 'assert';
import { describe, it } from 'node:test';
import { ISecretStorage, SessionManager } from '../sessionManager';

class MockSecretStorage implements ISecretStorage {
  private storage = new Map<string, string>();

  async get(key: string): Promise<string | undefined> {
    return this.storage.get(key);
  }

  async store(key: string, value: string): Promise<void> {
    this.storage.set(key, value);
  }

  async delete(key: string): Promise<void> {
    this.storage.delete(key);
  }
}

describe('SessionManager Unit Tests', () => {
  it('should store, retrieve, and delete refresh token', async () => {
    const mockStorage = new MockSecretStorage();
    const manager = new SessionManager(mockStorage);

    assert.strictEqual(await manager.getRefreshToken(), undefined);

    await manager.setRefreshToken('test-refresh-token-123');
    assert.strictEqual(await manager.getRefreshToken(), 'test-refresh-token-123');

    await manager.setUsername('test_dev');
    assert.strictEqual(await manager.getUsername(), 'test_dev');

    await manager.clear();
    assert.strictEqual(await manager.getRefreshToken(), undefined);
    assert.strictEqual(await manager.getUsername(), undefined);
  });
});
