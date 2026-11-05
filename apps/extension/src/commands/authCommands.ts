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
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Registration failed';
    vscode.window.showErrorMessage(`XiVault: ${msg}`);
    return;
  }

  // Ask to upload the opened contents to storage
  const activeEditor = vscode.window.activeTextEditor;
  if (activeEditor && activeEditor.document.getText().trim().length > 0) {
    const confirm = await vscode.window.showInformationMessage(
      'Upload the opened contents to storage?',
      { modal: true },
      'Yes'
    );

    if (confirm === 'Yes') {
      try {
        const text = activeEditor.document.getText();
        let displayPath = vscode.workspace.asRelativePath(activeEditor.document.uri, false).replace(/\\/g, '/');
        if (!displayPath || activeEditor.document.isUntitled) {
          const lang = activeEditor.document.languageId;
          const ext = lang ? (lang === 'typescript' ? '.ts' : lang === 'python' ? '.py' : `.${lang}`) : '.txt';
          displayPath = `snippet${ext}`;
        }

        const buffer = Buffer.from(text, 'utf-8');
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: `XiVault: Uploading ${displayPath}...`
          },
          async () => {
            await apiClient.uploadFile(displayPath, buffer);
            treeProvider.refresh();
          }
        );
        vscode.window.showInformationMessage('Successfully stored');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    }
  } else {
    vscode.window.showInformationMessage(
      `XiVault: Account registered for ${username}. (Open a file to upload contents to storage)`
    );
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
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Login failed';
    vscode.window.showErrorMessage(`XiVault: ${msg}`);
    return;
  }

  // Ask to download stored code with Enter for yes, esc for no
  const answer = await vscode.window.showInformationMessage(
    'Download the stored code with Enter for yes esc for no',
    { modal: true },
    'Yes'
  );

  if (answer === 'Yes') {
    try {
      const files = await apiClient.listFiles();
      if (files.length === 0) {
        vscode.window.showInformationMessage('XiVault: Your vault is empty. No stored code to download.');
        return;
      }

      let fileToDownload = files[0];
      if (files.length > 1) {
        const picked = await vscode.window.showQuickPick(
          files.map((f) => ({
            label: f.display_path,
            description: `${(f.byte_size / 1024).toFixed(1)} KB • ${f.language}`,
            file: f
          })),
          { placeHolder: 'Select stored code file to download and paste' }
        );
        if (!picked) {
          return;
        }
        fileToDownload = picked.file;
      }

      const content = await apiClient.downloadFile(fileToDownload.id);

      let applied = false;
      const activeEditor = vscode.window.activeTextEditor;
      if (activeEditor) {
        // Attempt to paste into currently opened file
        applied = await activeEditor.edit((editBuilder) => {
          const doc = activeEditor.document;
          const firstLine = doc.lineAt(0);
          const lastLine = doc.lineAt(doc.lineCount - 1);
          const fullRange = new vscode.Range(firstLine.range.start, lastLine.range.end);
          editBuilder.replace(fullRange, content);
        });
      }

      if (applied) {
        vscode.window.showInformationMessage(`XiVault: Stored code "${fileToDownload.display_path}" successfully pasted into opened file.`);
      } else {
        // Fallback: Open a new text editor with the content if active editor is absent or refused edit
        const doc = await vscode.workspace.openTextDocument({
          content,
          language: fileToDownload.language || 'plaintext'
        });
        await vscode.window.showTextDocument(doc);
        vscode.window.showInformationMessage(`XiVault: Stored code "${fileToDownload.display_path}" opened in editor.`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Download failed';
      vscode.window.showErrorMessage(`XiVault: ${msg}`);
    }
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
