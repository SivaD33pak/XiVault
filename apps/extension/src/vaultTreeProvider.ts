import * as vscode from 'vscode';
import { ApiClient, QuotaInfo, StoredFile } from './apiClient';
import { SessionManager } from './sessionManager';

export class VaultTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly fileInfo?: StoredFile,
    public readonly isHeader: boolean = false
  ) {
    super(label, collapsibleState);

    if (isHeader) {
      this.iconPath = new vscode.ThemeIcon('database');
      this.contextValue = 'vaultHeader';
    } else if (fileInfo) {
      this.iconPath = new vscode.ThemeIcon('file-code');
      this.contextValue = 'vaultFile';
      this.description = `${(fileInfo.byte_size / 1024).toFixed(1)} KB • ${fileInfo.language}`;
      this.tooltip = `Path: ${fileInfo.display_path}\nUploaded: ${new Date(fileInfo.created_at).toLocaleString()}`;
      this.command = {
        command: 'xivault.downloadFile',
        title: 'View File',
        arguments: [fileInfo]
      };
    }
  }
}

export class VaultTreeProvider implements vscode.TreeDataProvider<VaultTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<VaultTreeItem | undefined | void> =
    new vscode.EventEmitter<VaultTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<VaultTreeItem | undefined | void> =
    this._onDidChangeTreeData.event;

  private files: StoredFile[] = [];
  private quota: QuotaInfo | null = null;
  private username: string | null = null;

  constructor(
    private readonly apiClient: ApiClient,
    private readonly sessionManager: SessionManager
  ) {}

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: VaultTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: VaultTreeItem): Promise<VaultTreeItem[]> {
    if (element) {
      return [];
    }

    const refreshToken = await this.sessionManager.getRefreshToken();
    if (!refreshToken && !this.apiClient.isAuthenticated()) {
      const loginItem = new VaultTreeItem(
        'Click here to Login or Signup',
        vscode.TreeItemCollapsibleState.None
      );
      loginItem.iconPath = new vscode.ThemeIcon('key');
      loginItem.command = {
        command: 'xivault.startFlow',
        title: 'Login or Signup'
      };
      return [loginItem];
    }

    try {
      if (!this.apiClient.isAuthenticated()) {
        const refreshed = await this.apiClient.tryRefresh();
        if (!refreshed) {
          const authItem = new VaultTreeItem('Session expired. Click to Login or Signup.', vscode.TreeItemCollapsibleState.None);
          authItem.iconPath = new vscode.ThemeIcon('warning');
          authItem.command = { command: 'xivault.startFlow', title: 'Login or Signup' };
          return [authItem];
        }
      }

      this.username = (await this.sessionManager.getUsername()) || 'User';
      this.quota = await this.apiClient.getQuota();
      this.files = await this.apiClient.listFiles();

      const usedKb = (this.quota.used_bytes / 1024).toFixed(1);
      const totalMb = (this.quota.quota_bytes / (1024 * 1024)).toFixed(0);

      const headerItem = new VaultTreeItem(
        `${this.username} (${usedKb} KB / ${totalMb} MB used)`,
        vscode.TreeItemCollapsibleState.None,
        undefined,
        true
      );

      const fileItems = this.files.map(
        (f) => new VaultTreeItem(f.display_path, vscode.TreeItemCollapsibleState.None, f)
      );

      return [headerItem, ...fileItems];
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Error loading vault';
      const errorItem = new VaultTreeItem(message, vscode.TreeItemCollapsibleState.None);
      errorItem.iconPath = new vscode.ThemeIcon('error');
      return [errorItem];
    }
  }
}
