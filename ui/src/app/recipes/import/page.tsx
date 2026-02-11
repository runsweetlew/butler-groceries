'use client';

import { useState, useContext, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { importRecipe, bulkImport, importFromPhoto } from '@/lib/api';
import { UserContext } from '@/lib/user-context';

export default function ImportPage() {
  const router = useRouter();
  const { currentUser } = useContext(UserContext);
  const [mode, setMode] = useState<'single' | 'photo' | 'bulk'>('single');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">📥 Import Recipes</h1>

      {/* Mode Toggle */}
      <div className="flex gap-2">
        {([
          { key: 'single', label: '🔗 URL', desc: 'Paste a link' },
          { key: 'photo', label: '📸 Photo', desc: 'Snap a recipe' },
          { key: 'bulk', label: '📋 Bulk', desc: 'Multiple URLs' },
        ] as const).map(m => (
          <button
            key={m.key}
            className={`px-4 py-2 rounded-lg font-medium flex-1 text-center transition-colors ${
              mode === m.key ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
            onClick={() => setMode(m.key)}
          >
            <div>{m.label}</div>
            <div className="text-xs opacity-75">{m.desc}</div>
          </button>
        ))}
      </div>

      {mode === 'single' && (
        <URLImport
          currentUser={currentUser}
          loading={loading}
          setLoading={setLoading}
          results={results}
          setResults={setResults}
        />
      )}
      {mode === 'photo' && (
        <PhotoImport
          currentUser={currentUser}
          loading={loading}
          setLoading={setLoading}
          results={results}
          setResults={setResults}
        />
      )}
      {mode === 'bulk' && (
        <BulkImport
          currentUser={currentUser}
          loading={loading}
          setLoading={setLoading}
          results={results}
          setResults={setResults}
        />
      )}

      {/* Results */}
      <ImportResults results={results} router={router} />

      {/* Tips */}
      <div className="card p-5 bg-brand-50 border-brand-200">
        <h3 className="font-semibold text-brand-700 mb-2">💡 Import Tips</h3>
        <ul className="space-y-1 text-sm text-brand-800">
          <li>• <strong>URL:</strong> Works with NYT Cooking, Bon Appétit, Serious Eats, AllRecipes, food blogs, and more</li>
          <li>• <strong>Photo:</strong> Snap a cookbook page, recipe card, handwritten note, or screenshot</li>
          <li>• <strong>Bulk:</strong> Paste multiple URLs to import them all at once</li>
          <li>• You can edit any recipe after import to fix details</li>
          <li>• Proteins and cuisines are auto-tagged for the meal planner</li>
        </ul>
      </div>
    </div>
  );
}

// ---------- URL Import ----------
function URLImport({ currentUser, loading, setLoading, results, setResults }: any) {
  const [url, setUrl] = useState('');

  const handleImport = async () => {
    if (!url.trim()) return;
    setLoading(true);
    setResults([]);
    try {
      const result = await importRecipe(url.trim(), currentUser?.id);
      setResults([result]);
      if (result.status === 'success') setUrl('');
    } catch (e: any) {
      setResults([{ status: 'failed', url, error: e.message }]);
    }
    setLoading(false);
  };

  return (
    <div className="card p-5">
      <p className="text-gray-600 mb-4">
        Paste a recipe URL and we&apos;ll extract everything automatically — title, ingredients, steps, times, and photo.
      </p>
      <div className="flex gap-2">
        <input
          className="input flex-1"
          placeholder="https://www.seriouseats.com/best-chicken-recipe..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleImport()}
          disabled={loading}
        />
        <button onClick={handleImport} disabled={loading || !url.trim()} className="btn-primary whitespace-nowrap">
          {loading ? '⏳ Importing...' : '📥 Import'}
        </button>
      </div>
    </div>
  );
}

// ---------- Photo Import ----------
function PhotoImport({ currentUser, loading, setLoading, results, setResults }: any) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setResults([{ status: 'failed', error: 'Please select an image file' }]);
      return;
    }
    setSelectedFile(file);
    setResults([]);
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleImport = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setResults([]);
    try {
      const result = await importFromPhoto(selectedFile, currentUser?.id);
      setResults([result]);
      if (result.status === 'success') {
        setSelectedFile(null);
        setPreview(null);
      }
    } catch (e: any) {
      setResults([{ status: 'failed', error: e.message }]);
    }
    setLoading(false);
  };

  const handleClear = () => {
    setSelectedFile(null);
    setPreview(null);
    setResults([]);
  };

  return (
    <div className="card p-5 space-y-4">
      <p className="text-gray-600">
        📸 Take a photo or upload an image of a recipe — cookbook page, recipe card, handwritten note, magazine clipping, or screenshot.
      </p>

      {/* Hidden inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />

      {!preview ? (
        <>
          {/* Drop zone */}
          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
              dragOver ? 'border-brand-500 bg-brand-50' : 'border-gray-300 hover:border-brand-400 hover:bg-gray-50'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="text-4xl mb-3">📷</div>
            <p className="font-medium text-gray-700">
              Drop an image here or click to browse
            </p>
            <p className="text-sm text-gray-400 mt-1">JPEG, PNG, WebP — up to 20MB</p>
          </div>

          {/* Camera button (mobile-friendly) */}
          <button
            onClick={() => cameraInputRef.current?.click()}
            className="w-full py-3 bg-gray-100 hover:bg-gray-200 rounded-xl font-medium text-gray-700 transition-colors flex items-center justify-center gap-2"
          >
            <span className="text-xl">📱</span>
            Take Photo with Camera
          </button>
        </>
      ) : (
        /* Preview */
        <div className="space-y-3">
          <div className="relative">
            <img
              src={preview}
              alt="Recipe preview"
              className="w-full max-h-96 object-contain rounded-lg bg-gray-100"
            />
            <button
              onClick={handleClear}
              className="absolute top-2 right-2 w-8 h-8 bg-black/50 hover:bg-black/70 text-white rounded-full flex items-center justify-center text-sm"
            >
              ✕
            </button>
          </div>

          <div className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2">
            <div className="text-sm text-gray-600">
              📎 {selectedFile?.name}
              <span className="text-gray-400 ml-2">
                ({(selectedFile?.size ?? 0 / 1024 / 1024).toFixed(1)} bytes)
              </span>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleImport}
              disabled={loading}
              className="btn-primary flex-1 py-3 text-base"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin">🤔</span>
                  Claude is reading the recipe...
                </span>
              ) : (
                '✨ Extract Recipe with AI'
              )}
            </button>
            <button
              onClick={handleClear}
              disabled={loading}
              className="btn-secondary px-4"
            >
              Clear
            </button>
          </div>

          {loading && (
            <div className="text-center text-sm text-gray-500 animate-pulse">
              This takes 5-15 seconds depending on the image complexity...
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- Bulk Import ----------
function BulkImport({ currentUser, loading, setLoading, results, setResults }: any) {
  const [bulkUrls, setBulkUrls] = useState('');

  const handleImport = async () => {
    const urls = bulkUrls.split('\n').map((u: string) => u.trim()).filter(Boolean);
    if (!urls.length) return;
    setLoading(true);
    setResults([]);
    try {
      const results = await bulkImport(urls, currentUser?.id);
      setResults(results);
    } catch (e: any) {
      setResults([{ status: 'failed', error: e.message }]);
    }
    setLoading(false);
  };

  return (
    <div className="card p-5">
      <p className="text-gray-600 mb-4">
        Paste multiple URLs (one per line) to import them all at once.
      </p>
      <textarea
        className="input mb-3"
        placeholder={"https://recipe1.com/...\nhttps://recipe2.com/...\nhttps://recipe3.com/..."}
        value={bulkUrls}
        onChange={(e) => setBulkUrls(e.target.value)}
        rows={6}
        disabled={loading}
      />
      <button
        onClick={handleImport}
        disabled={loading || !bulkUrls.trim()}
        className="btn-primary w-full"
      >
        {loading ? '⏳ Importing...' : `📥 Import ${bulkUrls.split('\n').filter((u: string) => u.trim()).length} URLs`}
      </button>
    </div>
  );
}

// ---------- Results ----------
function ImportResults({ results, router }: { results: any[]; router: any }) {
  if (!results.length) return null;

  return (
    <div className="card p-5">
      <h3 className="font-semibold mb-3">Import Results</h3>
      <div className="space-y-2">
        {results.map((r, i) => (
          <div
            key={i}
            className={`p-3 rounded-lg ${r.status === 'success' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span>{r.status === 'success' ? '✅' : '❌'}</span>
              <span className="font-medium">
                {r.status === 'success' ? r.recipe_title : 'Import Failed'}
              </span>
              {r.extraction_method && (
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  r.extraction_method === 'photo'
                    ? 'bg-purple-100 text-purple-700'
                    : r.extraction_method === 'ai'
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {r.extraction_method === 'photo' ? '📸 photo' : r.extraction_method}
                </span>
              )}
              {r.duration_ms && (
                <span className="text-xs text-gray-400">{(r.duration_ms / 1000).toFixed(1)}s</span>
              )}
            </div>
            {r.error && <p className="text-sm text-red-600 mt-1">{r.error}</p>}
            {r.status === 'success' && (
              <button
                onClick={() => router.push(`/recipes/${r.recipe_id}`)}
                className="text-sm text-brand-500 hover:underline mt-1"
              >
                View Recipe →
              </button>
            )}
          </div>
        ))}
      </div>

      {results.length > 1 && (
        <div className="mt-3 pt-3 border-t border-gray-200 text-sm text-gray-600">
          {results.filter((r: any) => r.status === 'success').length} succeeded,{' '}
          {results.filter((r: any) => r.status === 'failed').length} failed
        </div>
      )}
    </div>
  );
}
