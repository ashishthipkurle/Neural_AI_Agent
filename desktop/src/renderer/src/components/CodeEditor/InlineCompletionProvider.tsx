
import * as monaco from 'monaco-editor';

export function registerInlineCompletionProvider(editor: monaco.editor.IStandaloneCodeEditor) {
    const provider = monaco.languages.registerInlineCompletionsProvider('*', {
        provideInlineCompletions: async (model, position, context, token) => {
            try {
                if (token?.isCancellationRequested) return { items: [] };
                // Simple debounce happens naturally by network latency + user typing speed
                // For production, a real debouncer wrapper is better, but this works for proof of concept
                const response = await fetch('http://localhost:8000/api/copilot/suggest', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        file_content: model.getValue(),
                        cursor_line: position.lineNumber,
                        cursor_column: position.column,
                        language: model.getLanguageId()
                    })
                });

                if (!response.ok) return { items: [] };

                if (token?.isCancellationRequested) return { items: [] };

                const data = await response.json();

                if (token?.isCancellationRequested) return { items: [] };

                if (data.suggestions && data.suggestions.length > 0) {
                    const text = data.suggestions[0].text;
                    return {
                        items: [{
                            insertText: text,
                            range: new monaco.Range(
                                position.lineNumber,
                                position.column,
                                position.lineNumber,
                                position.column
                            )
                        }]
                    };
                }
            } catch (e) {
                console.error("Copilot suggest error:", e);
            }

            return { items: [] };
        },
        disposeInlineCompletions: () => {
            // No resources to dispose.
        }
    });

    return provider;
}
