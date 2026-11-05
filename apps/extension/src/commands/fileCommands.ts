import * as vscode from 'vscode';
import { ApiClient, StoredFile } from '../apiClient';
import { VaultTreeItem, VaultTreeProvider } from '../vaultTreeProvider';

export function registerFileCommands(
  context: vscode.ExtensionContext,
  apiClient: ApiClient,
  treeProvider: VaultTreeProvider
): void {
  // 1. Upload File Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.uploadFile', async () => {
      const uris = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        canSelectMany: false,
        openLabel: 'Select File to Upload'
      });

      if (!uris || uris.length === 0) {
        return;
      }

      const fileUri = uris[0];
      const fileStat = await vscode.workspace.fs.stat(fileUri);

      // Preflight check: 1 MiB limit
      if (fileStat.size > 1048576) {
        vscode.window.showErrorMessage('XiVault: File exceeds the maximum 1 MiB size limit.');
        return;
      }

      const displayPath = vscode.workspace.asRelativePath(fileUri, false).replace(/\\/g, '/');
      const sizeKb = (fileStat.size / 1024).toFixed(1);

      const confirm = await vscode.window.showInformationMessage(
        `Upload "${displayPath}" (${sizeKb} KB) to your private XiVault?`,
        'Upload',
        'Cancel'
      );

      if (confirm !== 'Upload') {
        return;
      }

      try {
        const fileContent = await vscode.workspace.fs.readFile(fileUri);
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: `XiVault: Uploading ${displayPath}...`
          },
          async () => {
            await apiClient.uploadFile(displayPath, fileContent);
            treeProvider.refresh();
          }
        );
        vscode.window.showInformationMessage(`XiVault: Successfully uploaded ${displayPath}.`);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Upload failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    })
  );

  // 2. Download / View File Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.downloadFile', async (item?: VaultTreeItem | StoredFile) => {
      let file: StoredFile | undefined;

      if (item instanceof VaultTreeItem) {
        file = item.fileInfo;
      } else if (item && 'id' in item) {
        file = item;
      }

      if (!file) {
        // Prompt user from file list
        try {
          const files = await apiClient.listFiles();
          if (files.length === 0) {
            vscode.window.showInformationMessage('XiVault: Your vault is empty.');
            return;
          }
          const selected = await vscode.window.showQuickPick(
            files.map((f) => ({
              label: f.display_path,
              description: `${(f.byte_size / 1024).toFixed(1)} KB • ${f.language}`,
              file: f
            })),
            { placeHolder: 'Select a file to retrieve' }
          );
          if (!selected) {
            return;
          }
          file = selected.file;
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Failed to list files';
          vscode.window.showErrorMessage(`XiVault: ${msg}`);
          return;
        }
      }

      try {
        const content = await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: `XiVault: Downloading ${file.display_path}...`
          },
          async () => {
            return await apiClient.downloadFile(file!.id);
          }
        );

        // Open as read-only text document in editor
        const doc = await vscode.workspace.openTextDocument({
          content,
          language: file.language
        });
        await vscode.window.showTextDocument(doc, { preview: true });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Download failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    })
  );

  // 3. Delete File Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.deleteFile', async (item?: VaultTreeItem | StoredFile) => {
      let file: StoredFile | undefined;

      if (item instanceof VaultTreeItem) {
        file = item.fileInfo;
      } else if (item && 'id' in item) {
        file = item;
      }

      if (!file) {
        try {
          const files = await apiClient.listFiles();
          if (files.length === 0) {
            vscode.window.showInformationMessage('XiVault: Your vault is empty.');
            return;
          }
          const selected = await vscode.window.showQuickPick(
            files.map((f) => ({
              label: f.display_path,
              description: `${(f.byte_size / 1024).toFixed(1)} KB`,
              file: f
            })),
            { placeHolder: 'Select a file to delete' }
          );
          if (!selected) {
            return;
          }
          file = selected.file;
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : 'Failed to retrieve files';
          vscode.window.showErrorMessage(`XiVault: ${msg}`);
          return;
        }
      }

      const confirm = await vscode.window.showWarningMessage(
        `Are you sure you want to permanently delete "${file.display_path}" from XiVault?`,
        { modal: true },
        'Delete'
      );

      if (confirm !== 'Delete') {
        return;
      }

      try {
        await apiClient.deleteFile(file.id);
        treeProvider.refresh();
        vscode.window.showInformationMessage(`XiVault: Successfully deleted ${file.display_path}.`);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Delete failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    })
  );

  // 4. Search Files Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.searchFiles', async () => {
      const query = await vscode.window.showInputBox({
        prompt: 'Search vault files by path or indexed content',
        placeHolder: 'e.g. auth, api_key, function'
      });

      if (!query || !query.trim()) {
        return;
      }

      try {
        const results = await apiClient.searchFiles(query.trim());
        if (results.length === 0) {
          vscode.window.showInformationMessage(`XiVault: No files matched "${query}".`);
          return;
        }

        const picked = await vscode.window.showQuickPick(
          results.map((f) => ({
            label: f.display_path,
            description: f.excerpt ? `Excerpt: ${f.excerpt}` : `${f.language} • ${(f.byte_size / 1024).toFixed(1)} KB`,
            file: f
          })),
          { placeHolder: `Found ${results.length} result(s) for "${query}"` }
        );

        if (picked) {
          vscode.commands.executeCommand('xivault.downloadFile', picked.file);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Search failed';
        vscode.window.showErrorMessage(`XiVault: ${msg}`);
      }
    })
  );

  // 5. Refresh Files Command
  context.subscriptions.push(
    vscode.commands.registerCommand('xivault.refreshFiles', () => {
      treeProvider.refresh();
    })
  );
}
