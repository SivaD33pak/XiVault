import * as vscode from 'vscode';
import { ApiClient } from './apiClient';
import { registerAuthCommands, startAuthFlow } from './commands/authCommands';
import { registerFileCommands } from './commands/fileCommands';
import { SessionManager } from './sessionManager';
import { VaultTreeProvider } from './vaultTreeProvider';

export function activate(context: vscode.ExtensionContext): void {
  const sessionManager = new SessionManager(context.secrets);
  const apiClient = new ApiClient(sessionManager);
  const treeProvider = new VaultTreeProvider(apiClient, sessionManager);

  // Register TreeDataProvider for Activity Bar view
  vscode.window.registerTreeDataProvider('xivault.vaultView', treeProvider);

  // Register Auth and File commands
  registerAuthCommands(context, apiClient, treeProvider);
  registerFileCommands(context, apiClient, treeProvider);

  // Check existing session or prompt onboarding flow
  sessionManager.getRefreshToken().then(async (refreshToken) => {
    if (refreshToken) {
      const restored = await apiClient.tryRefresh();
      if (restored) {
        treeProvider.refresh();
      }
    } else {
      // First download / unauthenticated state: prompt Login / Signup flow
      await startAuthFlow(apiClient, treeProvider);
    }
  });
}

export function deactivate(): void {
  // Clean up resources if necessary
}
