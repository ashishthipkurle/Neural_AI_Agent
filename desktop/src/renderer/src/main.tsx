import { createRoot } from "react-dom/client";
import App from "./App";
import VoiceOverlay from "./components/VoiceOverlay";
import "./index.css";

function formatUnknownError(err: unknown): string {
	if (err instanceof Error) return `${err.name}: ${err.message}\n${err.stack ?? ''}`.trim();
	try {
		return typeof err === 'string' ? err : JSON.stringify(err, null, 2);
	} catch {
		return String(err);
	}
}

function showFatalOverlay(title: string, err: unknown) {
	const root = document.getElementById('root');
	const message = formatUnknownError(err);

	const overlay = document.createElement('div');
	overlay.style.position = 'fixed';
	overlay.style.inset = '0';
	overlay.style.zIndex = '2147483647';
	overlay.style.background = '#050505';
	overlay.style.color = '#e5e7eb';
	overlay.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
	overlay.style.padding = '16px';
	overlay.style.overflow = 'auto';

	overlay.innerHTML = `
		<div style="max-width: 960px; margin: 0 auto;">
			<div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">${title}</div>
			<pre style="white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.4; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 12px;">${message.replace(/</g, '&lt;')}</pre>
			<div style="margin-top: 10px; font-size: 12px; opacity: 0.7;">Press F12 to open DevTools (if available) for full logs.</div>
		</div>
	`;

	// If React already mounted partially, keep it but ensure overlay is visible.
	document.body.appendChild(overlay);

	// Keep the original fallback text if root exists; do not clear it.
	if (!root) {
		console.error('Renderer root element (#root) not found');
	}
}

window.addEventListener('error', (event) => {
	showFatalOverlay('Renderer error', (event as ErrorEvent).error ?? (event as ErrorEvent).message);
});

window.addEventListener('unhandledrejection', (event) => {
	showFatalOverlay('Unhandled promise rejection', (event as PromiseRejectionEvent).reason);
});

try {
	const rootEl = document.getElementById('root');
	if (!rootEl) {
		showFatalOverlay('Fatal', 'Missing #root element in index.html');
	} else {
		if (window.location.hash === '#/overlay') {
			createRoot(rootEl).render(<VoiceOverlay />);
		} else {
			createRoot(rootEl).render(<App />);
		}
	}
} catch (err) {
	showFatalOverlay('Fatal during startup', err);
}
