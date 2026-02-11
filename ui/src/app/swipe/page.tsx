'use client';

import { useState, useEffect, useContext } from 'react';
import { motion, useMotionValue, useTransform, PanInfo } from 'framer-motion';
import { createSwipeSession, getNextCard, submitSwipe, getSwipeSession, getMatches, getActiveSessions } from '@/lib/api';
import { UserContext } from '@/lib/user-context';
import Link from 'next/link';

export default function SwipePage() {
  const { currentUser } = useContext(UserContext);
  const [session, setSession] = useState<any>(null);
  const [card, setCard] = useState<any>(null);
  const [matches, setMatches] = useState<any[]>([]);
  const [showMatch, setShowMatch] = useState<any>(null);
  const [activeSessions, setActiveSessions] = useState<any[]>([]);
  const [context, setContext] = useState('dinner');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    getActiveSessions().then(setActiveSessions).catch(() => {});
  }, []);

  const startSession = async (existingId?: number) => {
    setLoading(true);
    try {
      let sess;
      if (existingId) {
        sess = await getSwipeSession(existingId, currentUser?.id);
      } else {
        sess = await createSwipeSession({ context, pool_size: 15 });
      }
      setSession(sess);
      await loadNextCard(sess.id);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const loadNextCard = async (sessionId: number) => {
    try {
      const c = await getNextCard(sessionId, currentUser?.id);
      setCard(c);
      setDone(false);
    } catch {
      setCard(null);
      setDone(true);
      // Load matches
      const m = await getMatches(sessionId);
      setMatches(m);
    }
  };

  const handleSwipe = async (decision: string) => {
    if (!session || !card) return;

    const result = await submitSwipe(session.id, {
      recipe_id: card.recipe.id,
      user_id: currentUser?.id,
      decision,
    });

    if (result.match) {
      setShowMatch(card.recipe);
      setTimeout(() => setShowMatch(null), 2500);
    }

    await loadNextCard(session.id);
  };

  // No session yet — show setup
  if (!session) {
    return (
      <div className="space-y-6 max-w-md mx-auto">
        <h1 className="text-2xl font-bold text-center">🔥 Recipe Swipe</h1>
        <p className="text-center text-gray-500">
          Swipe right on recipes you want, left on ones you don&apos;t.
          When you and your partner both swipe right — it&apos;s a match! 🎉
        </p>

        {/* Join existing session */}
        {activeSessions.length > 0 && (
          <div className="card p-5">
            <h3 className="font-semibold mb-3">Active Sessions</h3>
            <div className="space-y-2">
              {activeSessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => startSession(s.id)}
                  className="w-full p-3 rounded-lg bg-brand-50 hover:bg-brand-100 text-left transition-colors"
                >
                  <div className="font-medium">Session #{s.id} — {s.context}</div>
                  <div className="text-sm text-gray-500">Started {new Date(s.created_at).toLocaleString()}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* New session */}
        <div className="card p-5">
          <h3 className="font-semibold mb-3">Start New Session</h3>
          <div className="space-y-3">
            <div>
              <label className="text-sm text-gray-600 block mb-1">What kind of meal?</label>
              <select className="input" value={context} onChange={(e) => setContext(e.target.value)}>
                <option value="dinner">🍽 Dinner</option>
                <option value="weeknight">⚡ Quick Weeknight</option>
                <option value="weekend">🌟 Weekend Special</option>
                <option value="date_night">💕 Date Night</option>
              </select>
            </div>
            <button onClick={() => startSession()} disabled={loading} className="btn-primary w-full">
              {loading ? '⏳ Loading...' : '🔥 Start Swiping'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Done swiping
  if (done) {
    return (
      <div className="space-y-6 max-w-md mx-auto">
        <h1 className="text-2xl font-bold text-center">Done! 🎉</h1>

        {matches.length > 0 ? (
          <div className="card p-5">
            <h3 className="font-semibold mb-3 text-center">
              You matched on {matches.length} recipe{matches.length !== 1 ? 's' : ''}!
            </h3>
            <div className="space-y-3">
              {matches.map((m, i) => (
                <Link
                  key={i}
                  href={`/recipes/${m.recipe.id}`}
                  className="flex items-center gap-3 p-3 rounded-lg bg-green-50 border border-green-200 hover:bg-green-100 transition-colors"
                >
                  <span className="text-2xl">{m.is_superlike ? '💕' : '❤️'}</span>
                  <div>
                    <div className="font-medium">{m.recipe.title}</div>
                    <div className="text-sm text-gray-500">{m.recipe.cuisine}</div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <div className="card p-8 text-center">
            <div className="text-4xl mb-3">😅</div>
            <p className="text-gray-500">No matches this time. Your partner may not have swiped yet!</p>
          </div>
        )}

        <button onClick={() => { setSession(null); setDone(false); setMatches([]); }} className="btn-secondary w-full">
          Start New Session
        </button>
      </div>
    );
  }

  // Swiping!
  return (
    <div className="max-w-md mx-auto">
      {/* Progress */}
      <div className="text-center text-sm text-gray-500 mb-4">
        Card {card?.card_index} of {card?.total_cards}
      </div>

      {/* Match overlay */}
      {showMatch && (
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0, opacity: 0 }}
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        >
          <div className="bg-white rounded-2xl p-8 text-center shadow-2xl">
            <div className="text-6xl mb-3">🎉</div>
            <h2 className="text-2xl font-bold text-brand-600 mb-2">It&apos;s a Match!</h2>
            <p className="text-gray-600">{showMatch.title}</p>
          </div>
        </motion.div>
      )}

      {/* Swipe Card */}
      {card && <SwipeCard card={card} onSwipe={handleSwipe} />}

      {/* Action Buttons */}
      <div className="flex justify-center gap-6 mt-6">
        <button
          onClick={() => handleSwipe('dislike')}
          className="w-16 h-16 rounded-full bg-red-100 hover:bg-red-200 flex items-center justify-center text-3xl transition-colors"
          title="Nope"
        >
          👎
        </button>
        <button
          onClick={() => handleSwipe('skip')}
          className="w-12 h-12 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-xl transition-colors self-center"
          title="Skip"
        >
          ⏭
        </button>
        <button
          onClick={() => handleSwipe('like')}
          className="w-16 h-16 rounded-full bg-green-100 hover:bg-green-200 flex items-center justify-center text-3xl transition-colors"
          title="Yes!"
        >
          👍
        </button>
        <button
          onClick={() => handleSwipe('superlike')}
          className="w-12 h-12 rounded-full bg-brand-100 hover:bg-brand-200 flex items-center justify-center text-xl transition-colors self-center"
          title="Super Like!"
        >
          ⭐
        </button>
      </div>

      <div className="text-center text-xs text-gray-400 mt-3">
        👈 Nope &nbsp;|&nbsp; Skip ⏭ &nbsp;|&nbsp; Yes! 👉 &nbsp;|&nbsp; ⭐ Super Like
      </div>
    </div>
  );
}


// ---------- Swipeable Card Component ----------

function SwipeCard({ card, onSwipe }: { card: any; onSwipe: (decision: string) => void }) {
  const x = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const likeOpacity = useTransform(x, [0, 100], [0, 1]);
  const nopeOpacity = useTransform(x, [-100, 0], [1, 0]);

  const handleDragEnd = (_: any, info: PanInfo) => {
    if (info.offset.x > 100) {
      onSwipe('like');
    } else if (info.offset.x < -100) {
      onSwipe('dislike');
    } else if (info.offset.y < -100) {
      onSwipe('superlike');
    }
  };

  const recipe = card.recipe;

  return (
    <motion.div
      className="swipe-card card cursor-grab active:cursor-grabbing relative"
      style={{ x, rotate }}
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={0.7}
      onDragEnd={handleDragEnd}
      whileDrag={{ scale: 1.02 }}
    >
      {/* Like/Nope overlays */}
      <motion.div
        style={{ opacity: likeOpacity }}
        className="absolute top-4 left-4 z-10 bg-green-500 text-white font-bold text-2xl px-4 py-1 rounded-lg rotate-[-12deg]"
      >
        YES! 👍
      </motion.div>
      <motion.div
        style={{ opacity: nopeOpacity }}
        className="absolute top-4 right-4 z-10 bg-red-500 text-white font-bold text-2xl px-4 py-1 rounded-lg rotate-[12deg]"
      >
        NOPE 👎
      </motion.div>

      {/* Recipe Image */}
      <div className="h-56 bg-brand-100 overflow-hidden">
        {recipe.image_url || recipe.image_path ? (
          <img
            src={recipe.image_path || recipe.image_url}
            alt={recipe.title}
            className="w-full h-full object-cover pointer-events-none"
            draggable={false}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl">🍽️</div>
        )}
      </div>

      {/* Recipe Info */}
      <div className="p-5">
        <h2 className="text-xl font-bold mb-2">{recipe.title}</h2>

        <div className="flex flex-wrap gap-2 text-sm text-gray-500 mb-3">
          {recipe.cuisine && <span className="badge bg-brand-100 text-brand-700">{recipe.cuisine}</span>}
          {recipe.total_time_min && <span>⏱ {recipe.total_time_min} min</span>}
          {recipe.difficulty && <span className="capitalize">📊 {recipe.difficulty}</span>}
        </div>

        {recipe.avg_rating && (
          <div className="flex items-center gap-1 mb-2">
            <span className="text-yellow-500">{'★'.repeat(Math.round(recipe.avg_rating))}</span>
            <span className="text-sm text-gray-400">({recipe.rating_count} ratings)</span>
          </div>
        )}

        {recipe.description && (
          <p className="text-sm text-gray-600 line-clamp-2">{recipe.description}</p>
        )}

        {recipe.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {recipe.tags.slice(0, 5).map((t: any) => (
              <span key={t.id} className="badge bg-gray-100 text-gray-500">{t.name}</span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
