import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

interface DriftGuardFile {
    file_path: string;
    health_score: number;
    status: string;
    status_emoji: string;
    top_risk: string;
    recommendation: string;
    documentation_drift_score: number;
    test_drift_score: number;
    complexity_growth_score: number;
    naming_consistency_score: number;
}

interface DriftGuardReport {
    repo: string;
    analysis_window_days: number;
    analyzed_at: string;
    files: DriftGuardFile[];
    summary: {
        total_files: number;
        critical_count: number;
        at_risk_count: number;
        watch_count: number;
        healthy_count: number;
        average_health_score: number;
    };
}

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let fileWatcher: vscode.FileSystemWatcher | undefined;

export function activate(context: vscode.ExtensionContext) {
    console.log('DriftGuard extension is now active');

    // Create diagnostic collection
    diagnosticCollection = vscode.languages.createDiagnosticCollection('driftguard');
    context.subscriptions.push(diagnosticCollection);

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.command = 'driftguard.openReport';
    context.subscriptions.push(statusBarItem);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('driftguard.refresh', () => {
            refreshDiagnostics();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('driftguard.openReport', () => {
            openLatestReport();
        })
    );

    // Initial load
    refreshDiagnostics();

    // Watch for new reports
    const config = vscode.workspace.getConfiguration('driftguard');
    if (config.get('autoRefresh', true)) {
        setupFileWatcher(context);
    }
}

function setupFileWatcher(context: vscode.ExtensionContext) {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        return;
    }

    const config = vscode.workspace.getConfiguration('driftguard');
    const reportPath = config.get('reportPath', 'output');
    const pattern = new vscode.RelativePattern(workspaceFolder, `${reportPath}/report_*.json`);

    fileWatcher = vscode.workspace.createFileSystemWatcher(pattern);
    
    fileWatcher.onDidCreate(() => {
        vscode.window.showInformationMessage('DriftGuard: New report detected, refreshing...');
        refreshDiagnostics();
    });

    fileWatcher.onDidChange(() => {
        refreshDiagnostics();
    });

    context.subscriptions.push(fileWatcher);
}

function getLatestReportPath(): string | null {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
        return null;
    }

    const config = vscode.workspace.getConfiguration('driftguard');
    const reportPath = config.get('reportPath', 'output');
    const outputDir = path.join(workspaceFolder.uri.fsPath, reportPath);

    if (!fs.existsSync(outputDir)) {
        return null;
    }

    const files = fs.readdirSync(outputDir)
        .filter(f => f.startsWith('report_') && f.endsWith('.json'))
        .map(f => ({
            name: f,
            path: path.join(outputDir, f),
            mtime: fs.statSync(path.join(outputDir, f)).mtime
        }))
        .sort((a, b) => b.mtime.getTime() - a.mtime.getTime());

    return files.length > 0 ? files[0].path : null;
}

function refreshDiagnostics() {
    diagnosticCollection.clear();

    const reportPath = getLatestReportPath();
    if (!reportPath) {
        statusBarItem.text = '🔍 DriftGuard: No report';
        statusBarItem.tooltip = 'Run DriftGuard analysis to generate a report';
        statusBarItem.show();
        return;
    }

    try {
        const reportContent = fs.readFileSync(reportPath, 'utf-8');
        const report: DriftGuardReport = JSON.parse(reportContent);

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return;
        }

        let issueCount = 0;

        for (const file of report.files) {
            // Only show diagnostics for CRITICAL and AT_RISK files
            if (file.status !== 'CRITICAL' && file.status !== 'AT_RISK') {
                continue;
            }

            issueCount++;

            const filePath = path.join(workspaceFolder.uri.fsPath, file.file_path);
            const fileUri = vscode.Uri.file(filePath);

            // Determine severity
            const severity = file.status === 'CRITICAL' 
                ? vscode.DiagnosticSeverity.Error 
                : vscode.DiagnosticSeverity.Warning;

            // Create diagnostic message
            const message = `DriftGuard: Health ${file.health_score}/100 — ${file.top_risk}`;
            
            // Create diagnostic at line 0
            const range = new vscode.Range(0, 0, 0, 0);
            const diagnostic = new vscode.Diagnostic(range, message, severity);
            diagnostic.source = 'DriftGuard';
            diagnostic.code = file.status;

            // Add detailed information
            const details = [
                `Status: ${file.status_emoji} ${file.status}`,
                `Health Score: ${file.health_score}/100`,
                ``,
                `Dimension Scores:`,
                `  Documentation: ${file.documentation_drift_score}/100`,
                `  Test Coverage: ${file.test_drift_score}/100`,
                `  Complexity: ${file.complexity_growth_score}/100`,
                `  Naming: ${file.naming_consistency_score}/100`,
                ``,
                `Top Risk: ${file.top_risk}`,
                `Recommendation: ${file.recommendation}`
            ].join('\n');

            diagnostic.relatedInformation = [
                new vscode.DiagnosticRelatedInformation(
                    new vscode.Location(fileUri, range),
                    details
                )
            ];

            diagnosticCollection.set(fileUri, [diagnostic]);
        }

        // Update status bar
        const emoji = report.summary.critical_count > 0 ? '🔴' : 
                     report.summary.at_risk_count > 0 ? '🟠' : '🟢';
        statusBarItem.text = `${emoji} DriftGuard: ${issueCount} issue${issueCount !== 1 ? 's' : ''}`;
        statusBarItem.tooltip = [
            `DriftGuard Analysis Summary`,
            ``,
            `Total Files: ${report.summary.total_files}`,
            `🔴 Critical: ${report.summary.critical_count}`,
            `🟠 At Risk: ${report.summary.at_risk_count}`,
            `🟡 Watch: ${report.summary.watch_count}`,
            `🟢 Healthy: ${report.summary.healthy_count}`,
            ``,
            `Average Score: ${report.summary.average_health_score.toFixed(1)}/100`,
            ``,
            `Click to open report`
        ].join('\n');
        statusBarItem.show();

        if (issueCount > 0) {
            vscode.window.showInformationMessage(
                `DriftGuard found ${issueCount} file${issueCount !== 1 ? 's' : ''} needing attention`,
                'View Report'
            ).then(selection => {
                if (selection === 'View Report') {
                    openLatestReport();
                }
            });
        }

    } catch (error) {
        console.error('Error reading DriftGuard report:', error);
        statusBarItem.text = '🔍 DriftGuard: Error';
        statusBarItem.tooltip = `Failed to read report: ${error}`;
        statusBarItem.show();
    }
}

function openLatestReport() {
    const reportPath = getLatestReportPath();
    if (!reportPath) {
        vscode.window.showWarningMessage('No DriftGuard report found. Run analysis first.');
        return;
    }

    vscode.workspace.openTextDocument(reportPath).then(doc => {
        vscode.window.showTextDocument(doc, { preview: false });
    });
}

export function deactivate() {
    if (fileWatcher) {
        fileWatcher.dispose();
    }
}

// Made with Bob
