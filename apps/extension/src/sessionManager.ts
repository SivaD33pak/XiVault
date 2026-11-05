export interface ISecretStorage {
  get(key: string): Thenable<string | undefined>;
  store(key: string, value: string): Thenable<void>;
  delete(key: string): Thenable<void>;
}

export class SessionManager {
  private static readonly REFRESH_TOKEN_KEY = 'xivault.refreshToken';
  private static readonly USERNAME_KEY = 'xivault.username';

  constructor(private readonly secretStorage: ISecretStorage) {}

  async getRefreshToken(): Promise<string | undefined> {
    return await this.secretStorage.get(SessionManager.REFRESH_TOKEN_KEY);
  }

  async setRefreshToken(token: string): Promise<void> {
    await this.secretStorage.store(SessionManager.REFRESH_TOKEN_KEY, token);
  }

  async getUsername(): Promise<string | undefined> {
    return await this.secretStorage.get(SessionManager.USERNAME_KEY);
  }

  async setUsername(username: string): Promise<void> {
    await this.secretStorage.store(SessionManager.USERNAME_KEY, username);
  }

  async clear(): Promise<void> {
    await this.secretStorage.delete(SessionManager.REFRESH_TOKEN_KEY);
    await this.secretStorage.delete(SessionManager.USERNAME_KEY);
  }
}
