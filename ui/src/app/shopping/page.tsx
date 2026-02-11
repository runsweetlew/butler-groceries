'use client';

import { useState, useEffect, useContext } from 'react';
import { getCurrentShoppingList, generateShoppingList, updateShoppingItem } from '@/lib/api';
import { UserContext } from '@/lib/user-context';
import { format, startOfWeek } from 'date-fns';

export default function ShoppingPage() {
  const { currentUser } = useContext(UserContext);
  const [list, setList] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    getCurrentShoppingList().then(setList).catch(() => null).finally(() => setLoading(false));
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    const weekOf = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
    try {
      const newList = await generateShoppingList({ week_of: weekOf, name: `Week of ${weekOf}` });
      setList(newList);
    } finally {
      setGenerating(false);
    }
  };

  const handleToggleItem = async (itemId: number, currentChecked: boolean) => {
    await updateShoppingItem(itemId, {
      checked: !currentChecked,
      checked_by: currentUser?.id,
    });
    // Update locally
    setList((prev: any) => ({
      ...prev,
      items: prev.items.map((i: any) =>
        i.id === itemId ? { ...i, checked: !currentChecked } : i
      ),
      checked_items: prev.checked_items + (currentChecked ? -1 : 1),
    }));
  };

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;

  // Group items by aisle
  const aisles: Record<string, any[]> = {};
  if (list?.items) {
    for (const item of list.items) {
      const aisle = item.aisle || '📦 Other';
      if (!aisles[aisle]) aisles[aisle] = [];
      aisles[aisle].push(item);
    }
  }

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">🛒 Shopping List</h1>
        <button onClick={handleGenerate} disabled={generating} className="btn-primary">
          {generating ? '⏳ Generating...' : '🔄 Generate from Plan'}
        </button>
      </div>

      {!list || list.id === 0 ? (
        <div className="card p-8 text-center">
          <div className="text-4xl mb-3">🛒</div>
          <h3 className="text-lg font-medium mb-2">No shopping list yet</h3>
          <p className="text-gray-500 mb-4">Plan some meals first, then generate your list.</p>
          <button onClick={handleGenerate} disabled={generating} className="btn-primary">
            Generate Shopping List
          </button>
        </div>
      ) : (
        <>
          {/* List Header */}
          <div className="card p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold">{list.name}</h2>
                <p className="text-sm text-gray-500">
                  {list.checked_items}/{list.total_items} items checked
                </p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-brand-600">
                  {Math.round((list.checked_items / Math.max(list.total_items, 1)) * 100)}%
                </div>
                <div className="text-xs text-gray-400">complete</div>
              </div>
            </div>
            {/* Progress bar */}
            <div className="h-2 bg-gray-200 rounded-full mt-3">
              <div
                className="h-full bg-green-500 rounded-full transition-all duration-300"
                style={{ width: `${(list.checked_items / Math.max(list.total_items, 1)) * 100}%` }}
              />
            </div>
          </div>

          {/* 🛒 Shop at Meijer */}
          {list.items?.length > 0 && (() => {
            const uncheckedItems = list.items.filter((i: any) => !i.checked);
            if (uncheckedItems.length === 0) return null;
            return (
              <div className="card p-4 bg-blue-50 border-blue-200">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-blue-800 text-sm">🛒 Shop at Meijer</h3>
                  <span className="text-xs text-blue-600">{uncheckedItems.length} items remaining</span>
                </div>
                <div className="space-y-1 mb-3">
                  {uncheckedItems.map((item: any) => (
                    <a
                      key={item.id}
                      href={`https://www.meijer.com/shopping/search.html?s=${encodeURIComponent(item.name)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-blue-200 hover:bg-blue-100 transition-colors text-sm"
                    >
                      <span className="text-blue-400">🔍</span>
                      <span className="text-gray-700">{item.name}</span>
                      {item.quantity && (
                        <span className="text-gray-400 text-xs ml-auto">{item.quantity} {item.unit}</span>
                      )}
                    </a>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Items by Aisle */}
          {Object.entries(aisles).map(([aisle, items]) => (
            <div key={aisle} className="card">
              <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
                <h3 className="font-semibold text-sm text-gray-600">{aisle}</h3>
              </div>
              <div className="divide-y divide-gray-50">
                {items.map((item: any) => (
                  <label
                    key={item.id}
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
                      item.checked ? 'opacity-50' : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={() => handleToggleItem(item.id, item.checked)}
                      className="w-5 h-5 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                    />
                    <span className={`flex-1 ${item.checked ? 'line-through text-gray-400' : ''}`}>
                      {item.name}
                    </span>
                    {item.quantity && (
                      <span className="text-sm text-gray-400">
                        {item.quantity} {item.unit}
                      </span>
                    )}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
