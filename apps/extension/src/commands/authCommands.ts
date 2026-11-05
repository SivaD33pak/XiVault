import * as vscode from 'vscode';
import { ApiClient } from '../apiClient';
import { VaultTreeProvider } from '../vaultTreeProvider';

export async function handleSignupFlow(
  apiClient: ApiClient,
  treeProvider: VaultTreeProvider
): Promise<void> {
  const username = await vscode.window.showInputBox({
    prompt: 'new username :',
    placeHolder: 'Enter new username (3-32 characters)',
    validateInput: (text) => {
      if (!/^[a-z0-9_-]{3,32}$/.test(text)) {
        return 'Username must be 3-32 characters: lowercase letters, digits, _ or -';
      }
      return null;
    }
  });
  if (!username) {
    return;
  }

  const password = await vscode.window.showInputBox({
    prompt: 'new password:',
    password: true,
    validateInput: (text) => {
      if (text.length < 6) {
        return 'Password must be at least 6 characters';
      }
      return null;
    }
  });
  if (!password) {
    return;
  }

  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'XiVault: Registering account...'
      },
      async () => {
        await apiClient.register(username, password);
        await apiClient.login(username, password);
        treeProvider.refresh();
      }
    );
    vscode.window.showInformationMessage(`XiVault: Account registered and logged in as ${username}.`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Registration failed';
    vscode.window.showErrorMessage(`XiVault: ${msg}`);
    return;
  }
}

export async function handleLoginFlow(
  apiClient: ApiClient,
  treeProvider: VaultTreeProvider
): Promise<void> {
  const username = await vscode.window.showInputBox({
    prompt: 'username :',
    placeHolder: 'Enter username'
  });
  if (!username) {
    return;
  }

  const password = await vscode.window.showInputBox({
    prompt: 'password:',
    password: true
  });
  if (!password) {
    return;
  }

  try {
    await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'XiVault: Logging in...'
      },
      async () => {
        await apiClient.login(username, password);
        treeProvider.refresh();
      }
    );
    vscode.window.showInformationMessage(`XiVault: Successfully logged in as ${username}.`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Login failed';
    vscode.window.showErrorMessage(`XiVault: ${msg}`);
    return;
  }
}

export async function startAuthFlow(
  apiClient: ApiClient,
  treeProvider: VaultTreeProvider
): Promise<void> {
  const selection = await vscode.window.showQuickPick(
    [
      { label: '$(sign-in) Login', description: 'Log in to your existing vault', action: 'login' },
      { label: '$(person-add) Signup', description: 'Create a new XiVault account', action: 'signup' }
    ],
    { placeHolder: 'Welcome to XiVault! Choose Login or Signup to proceed' }
  );

  if (!selection) {
    return;
  }

  if (selection.action === 'signup') {
    await handleSignupFlow(apiClient, treeProvider);
  } else {
    await handleLoginFlow(apiClient, treeProvider);
  }
}

export function registerAuthCommands(
  context: vscode.ExtensionContext,
  apiClient: ApiClient,
  treeProvider: VaultTreeProvider
): void {
  // Main Unified Login/Signup Flow
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.startFlow', async () => {
      await startAuthFlow(apiClient, treeProvider);
    })
  );

  // Register / Signup Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.register', async () => {
      await handleSignupFlow(apiClient, treeProvider);
    })
  );

  // Login Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.login', async () => {
      await handleLoginFlow(apiClient, treeProvider);
    })
  );

  // Logout Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.logout', async () => {
      try {
        await apiClient.logout();
        treeProvider.refresh();
        vscode.window.showInformationMessage('XiVault: Successfully logged out.');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Logout failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    })
  );
}
