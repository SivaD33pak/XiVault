import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';

export interface QuotaInfo {
  used_bytes: number;
  quota_bytes: number;
  remaining_bytes: number;
}

export interface StoredFile {
  id: string;
  display_path: string;
  language: string;
  byte_size: number;
  created_at: string;
  excerpt?: string;
}

export class ApiClient {
  private accessToken: string | null = null;

  constructor(private readonly sessionManager: SessionManager) {}

  private getBaseUrl(): string {
    const config = vscode.workspace.getConfiguration('xivault');
    let url = config.get<string>('apiBaseUrl', 'https://xivault.onrender.com/v1') || 'https://xivault.onrender.com/v1';
    url = url.trim();
    while (url.endsWith('/')) {
      url = url.slice(0, -1);
    }
    if (!url.endsWith('/v1')) {
      url = `${url}/v1`;
    }
    return url;
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  isAuthenticated(): boolean {
    return this.accessToken !== null;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    isRetry = false
  ): Promise<T> {
    const baseUrl = this.getBaseUrl();
    const url = `${baseUrl}${endpoint}`;

    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {})
    };

    if (this.accessToken && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(url, {
      ...options,
      headers
    });

    if (response.status === 401 && !isRetry && endpoint !== '/auth/login' && endpoint !== '/auth/refresh') {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        return this.request<T>(endpoint, options, true);
      }
    }

    if (!response.ok) {
      let errorMessage = `Request failed (${response.status})`;
      try {
        const errorData = (await response.json()) as { error?: { message?: string } };
        if (errorData?.error?.message) {
          errorMessage = errorData.error.message;
        }
      } catch {
        // Fall back to default
      }
      throw new Error(errorMessage);
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    return (await response.json()) as T;
  }

  async tryRefresh(): Promise<boolean> {
    const refreshToken = await this.sessionManager.getRefreshToken();
    if (!refreshToken) {
      this.accessToken = null;
      return false;
    }

    try {
      const baseUrl = this.getBaseUrl();
      const res = await fetch(`${baseUrl}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken })
      });

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          await this.sessionManager.clear();
          this.accessToken = null;
        }
        return false;
      }

      const data = (await res.json()) as { access_token: string; refresh_token: string };
      this.accessToken = data.access_token;
      await this.sessionManager.setRefreshToken(data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  async register(username: string, password: string): Promise<QuotaInfo> {
    const res = await this.request<{ quota: QuotaInfo }>('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    return res.quota;
  }

  async login(username: string, password: string): Promise<{ username: string; quota: QuotaInfo }> {
    const res = await this.request<{
      access_token: string;
      refresh_token: string;
      user: { username: string };
    }>('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    this.accessToken = res.access_token;
    await this.sessionManager.setRefreshToken(res.refresh_token);
    await this.sessionManager.setUsername(res.user.username);

    const quota = await this.getQuota();
    return { username: res.user.username, quota };
  }

  async logout(): Promise<void> {
    const refreshToken = await this.sessionManager.getRefreshToken();
    if (refreshToken && this.accessToken) {
      try {
        await this.request<void>('/auth/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken })
        });
      } catch {
        // Clear regardless of server error
      }
    }
    this.accessToken = null;
    await this.sessionManager.clear();
  }

  async getQuota(): Promise<QuotaInfo> {
    return await this.request<QuotaInfo>('/me/quota');
  }

  async listFiles(): Promise<StoredFile[]> {
    const res = await this.request<{ items: StoredFile[] }>('/files?limit=100');
    return res.items;
  }

  async searchFiles(query: string): Promise<StoredFile[]> {
    const res = await this.request<{ items: StoredFile[] }>(
      `/files/search?q=${encodeURIComponent(query)}&limit=50`
    );
    return res.items;
  }

  async uploadFile(displayPath: string, content: Uint8Array): Promise<void> {
    const formData = new FormData();
    formData.append('display_path', displayPath);
    const blob = new Blob([content], { type: 'text/plain' });
    formData.append('file', blob, displayPath.split('/').pop() || 'file.txt');

    await this.request('/files', {
      method: 'POST',
      body: formData
    });
  }

  async downloadFile(fileId: string, isRetry = false): Promise<string> {
    const baseUrl = this.getBaseUrl();
    if (!this.accessToken) {
      await this.tryRefresh();
    }

    const res = await fetch(`${baseUrl}/files/${fileId}/download`, {
      headers: {
        Authorization: `Bearer ${this.accessToken || ''}`
      }
    });

    if (res.status === 401 && !isRetry) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        return this.downloadFile(fileId, true);
      }
    }

    if (!res.ok) {
      throw new Error(`Failed to download file (${res.status})`);
    }

    return await res.text();
  }

  async deleteFile(fileId: string): Promise<void> {
    await this.request<void>(`/files/${fileId}`, {
      method: 'DELETE'
    });
  }
}
