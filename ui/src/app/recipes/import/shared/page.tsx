'use client';

import { useState, useEffect, useContext, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { importRecipe, importFromPhoto } from '@/lib/api';
import { UserContext } from '@/lib/user-context';

function ShareImportInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentUser } = useContext(UserContext);
  const [status, setStatus] = useState<'loading' | 'importing' | 'success' | 'error' | 'review'>('loading');
  const [result, setResult] = useState<any>(null);
  const [sharedUrl, setSharedUrl] = useState('');
  const [sharedText, setSharedText] = useState('');
  const [sharedTitle, setSharedTitle] = useState('');
  const [sharedFile, setSharedFile] = useState<File | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    // Extract shared data from URL params (GET fallback) or form data
    const url = searchParams.get('url') || '';
    const text = searchParams.get('text') || '';
    const title = searchParams.get('title') || '';

    // Try to extract a URL from the shared text (apps often put URL in text field)
    const extractedUrl = url || extractUrl(text) || extractUrl(title) || '';

    setSharedUrl(extractedUrl);
    setSharedText(text);
    setSharedTitle(title);

    if (extractedUrl) {
      // Auto-import if we have a URL
      setStatus('review');
    } else if (!url && !text && !title) {
      // Check if this was a POST with form data (files)
      // The browser handles multipart POST → we need to check for files via service worker
      // For now, redirect to import page with a message
      setStatus('review');
    } else {
      setStatus('review');
    }
  }, [searchParams]);

  const extractUrl = (text: string): string => {
    if (!text) return '';
    const urlMatch = text.match(/https?:\/\/[^\s<>"{}|\\^`\[\]]+/);
    return urlMatch ? urlMatch[0] : '';
  };

  const handleImport = async () => {
    if (!sharedUrl && !sharedFile) {
      setError('No recipe URL or photo found in shared content');
      setStatus('error');
      return;
    }

    setStatus('importing');
    try {
      let importResult;
      if (sharedFile) {
        importResult = await importFromPhoto(sharedFile, currentUser?.id);
      } else {
        importResult = await importRecipe(sharedUrl, currentUser?.id);
      }

      setResult(importResult);
      if (importResult.status === 'success') {
        setStatus('success');
      } else {
        setError(importResult.error || 'Import failed');
        setStatus('error');
      }
    } catch (e: any) {
      setError(e.message || 'Import failed');
      setStatus('error');
    }
  };

  // Auto-import on mount if we have a clear URL
  useEffect(() => {
    if (sharedUrl && status === 'review') {
      // Small delay so user can see what's happening
      const timer = setTimeout(() => handleImport(), 500);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sharedUrl, status]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card p-8 max-w-md w-full text-center space-y-4">
        {/* Loading */}
        {status === 'loading' && (
          <>
            <div className="text-5xl animate-bounce">📥</div>
            <p className="text-gray-600">Reading shared content...</p>
          </>
        )}

        {/* Importing */}
        {status === 'importing' && (
          <>
            <div className="text-5xl animate-spin">🍳</div>
            <h2 className="text-xl font-bold">Importing Recipe...</h2>
            {sharedUrl && (
              <p className="text-sm text-gray-500 break-all">{sharedUrl}</p>
            )}
            {sharedFile && (
              <p className="text-sm text-gray-500">📸 {sharedFile.name}</p>
            )}
            <p className="text-sm text-gray-400">This may take a few seconds</p>
          </>
        )}

        {/* Review (no auto-import) */}
        {status === 'review' && !sharedUrl && !sharedFile && (
          <>
            <div className="text-5xl">🤔</div>
            <h2 className="text-xl font-bold">What did you share?</h2>
            {sharedTitle && <p className="text-sm text-gray-600">Title: {sharedTitle}</p>}
            {sharedText && <p className="text-sm text-gray-500 break-all">{sharedText}</p>}
            <p className="text-gray-500 mt-2">
              No recipe URL found in the shared content.
            </p>
            <div className="space-y-2 pt-2">
              <input
                className="input w-full"
                placeholder="Paste a recipe URL..."
                value={sharedUrl}
                onChange={(e) => setSharedUrl(e.target.value)}
              />
              <button
                onClick={handleImport}
                disabled={!sharedUrl}
                className="btn-primary w-full disabled:opacity-50"
              >
                📥 Import
              </button>
              <button
                onClick={() => router.push('/recipes/import')}
                className="btn-secondary w-full"
              >
                Go to Import Page
              </button>
            </div>
          </>
        )}

        {/* Success */}
        {status === 'success' && result && (
          <>
            <div className="text-5xl">✅</div>
            <h2 className="text-xl font-bold">Recipe Imported!</h2>
            <p className="text-lg text-brand-600">{result.recipe_title}</p>
            <p className="text-sm text-gray-500">
              {result.extraction_method === 'photo' ? '📸' : result.extraction_method === 'ai' ? '🤖' : '⚡'}{' '}
              Imported in {(result.duration_ms / 1000).toFixed(1)}s
            </p>
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => router.push(`/recipes/${result.recipe_id}`)}
                className="btn-primary flex-1"
              >
                View Recipe
              </button>
              <button
                onClick={() => router.push('/recipes')}
                className="btn-secondary flex-1"
              >
                All Recipes
              </button>
            </div>
          </>
        )}

        {/* Error */}
        {status === 'error' && (
          <>
            <div className="text-5xl">😕</div>
            <h2 className="text-xl font-bold">Import Failed</h2>
            <p className="text-sm text-red-600">{error}</p>
            {sharedUrl && <p className="text-xs text-gray-400 break-all">{sharedUrl}</p>}
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => { setStatus('review'); setError(''); }}
                className="btn-primary flex-1"
              >
                Try Again
              </button>
              <button
                onClick={() => router.push('/recipes/import')}
                className="btn-secondary flex-1"
              >
                Manual Import
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function ShareImportPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-5xl animate-bounce">📥</div>
      </div>
    }>
      <ShareImportInner />
    </Suspense>
  );
}
