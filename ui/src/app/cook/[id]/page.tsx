'use client';

import { useState, useEffect, useCallback, useRef, useContext } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { getCookAlong, getScaledIngredients, createRating } from '@/lib/api';
import { UserContext } from '@/lib/user-context';

interface Timer {
  id: string;
  label: string;
  totalSeconds: number;
  remainingSeconds: number;
  running: boolean;
  stepNumber: number;
}

export default function CookAlongPage() {
  const params = useParams();
  const router = useRouter();
  const { currentUser } = useContext(UserContext);
  const [session, setSession] = useState<any>(null);
  const [ingredients, setIngredients] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [timers, setTimers] = useState<Timer[]>([]);
  const [multiplier, setMultiplier] = useState(1);
  const [showIngredients, setShowIngredients] = useState(false);
  const [showRating, setShowRating] = useState(false);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Wake Lock API — keep screen on
  const wakeLockRef = useRef<any>(null);
  useEffect(() => {
    const acquireWakeLock = async () => {
      try {
        if ('wakeLock' in navigator) {
          wakeLockRef.current = await (navigator as any).wakeLock.request('screen');
        }
      } catch (e) {
        console.log('Wake Lock not available');
      }
    };
    acquireWakeLock();
    return () => { wakeLockRef.current?.release(); };
  }, []);

  // Load cook-along data
  useEffect(() => {
    if (params.id) {
      Promise.all([
        getCookAlong(Number(params.id), multiplier),
        getScaledIngredients(Number(params.id), multiplier),
      ]).then(([s, i]) => {
        setSession(s);
        setIngredients(i);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [params.id, multiplier]);

  // Timer tick
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimers(prev => prev.map(t => {
        if (!t.running || t.remainingSeconds <= 0) return t;
        const newRemaining = t.remainingSeconds - 1;
        if (newRemaining <= 0) {
          // Timer done! Play sound / vibrate
          try {
            navigator.vibrate?.([200, 100, 200, 100, 200]);
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ==');
            audio.play().catch(() => {});
          } catch {}
        }
        return { ...t, remainingSeconds: newRemaining };
      }));
    }, 1000);

    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  const startTimer = (stepNumber: number, label: string, minutes: number) => {
    const id = `timer-${stepNumber}-${Date.now()}`;
    setTimers(prev => [...prev, {
      id,
      label,
      totalSeconds: minutes * 60,
      remainingSeconds: minutes * 60,
      running: true,
      stepNumber,
    }]);
  };

  const toggleTimer = (id: string) => {
    setTimers(prev => prev.map(t => t.id === id ? { ...t, running: !t.running } : t));
  };

  const removeTimer = (id: string) => {
    setTimers(prev => prev.filter(t => t.id !== id));
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const nextStep = () => {
    if (session && currentStep < session.steps.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      setShowRating(true);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) setCurrentStep(prev => prev - 1);
  };

  // Keyboard controls
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') { e.preventDefault(); nextStep(); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); prevStep(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [currentStep, session]);

  if (loading) return <div className="text-center py-12 text-gray-400">Preparing cook-along...</div>;
  if (!session) return <div className="text-center py-12 text-gray-400">Recipe not found</div>;

  const step = session.steps[currentStep];
  const progress = ((currentStep + 1) / session.steps.length) * 100;

  // Rating screen
  if (showRating) {
    return <FinishedScreen recipeId={Number(params.id)} recipeName={session.recipe_title} currentUser={currentUser} onDone={() => router.push(`/recipes/${params.id}`)} />;
  }

  return (
    <div className="min-h-[calc(100vh-120px)] flex flex-col screen-awake">
      {/* Progress Bar */}
      <div className="h-1.5 bg-gray-200 rounded-full mb-4">
        <div className="h-full bg-brand-500 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold truncate flex-1">{session.recipe_title}</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowIngredients(!showIngredients)} className="btn-secondary text-sm">
            {showIngredients ? 'Hide' : '📋 Ingredients'}
          </button>
          <button onClick={() => router.push(`/recipes/${params.id}`)} className="btn-secondary text-sm">✕</button>
        </div>
      </div>

      {/* Servings Multiplier */}
      <div className="flex items-center gap-2 mb-4 text-sm">
        <span className="text-gray-500">Servings:</span>
        {[0.5, 1, 1.5, 2, 3].map(m => (
          <button
            key={m}
            onClick={() => setMultiplier(m)}
            className={`px-2 py-1 rounded ${multiplier === m ? 'bg-brand-500 text-white' : 'bg-gray-100'}`}
          >
            {m}x
          </button>
        ))}
      </div>

      {/* Ingredients Drawer */}
      <AnimatePresence>
        {showIngredients && ingredients && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="card p-4 mb-4 overflow-hidden"
          >
            <h3 className="font-semibold mb-2">Ingredients ({ingredients.adjusted_servings} servings)</h3>
            <ul className="space-y-1 text-sm">
              {ingredients.ingredients?.map((ing: any, i: number) => (
                <li key={i} className="flex gap-2">
                  <span className="text-brand-400">•</span>
                  <span>
                    {ing.quantity && <strong>{ing.quantity} {ing.unit} </strong>}
                    {ing.raw_text}
                  </span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Active Timers */}
      {timers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {timers.map(t => (
            <div
              key={t.id}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-mono ${
                t.remainingSeconds <= 0 ? 'bg-red-100 text-red-700 animate-pulse' :
                t.running ? 'bg-brand-100 text-brand-700' : 'bg-gray-100 text-gray-600'
              }`}
            >
              <span>{t.label}: {formatTime(t.remainingSeconds)}</span>
              {t.remainingSeconds > 0 ? (
                <button onClick={() => toggleTimer(t.id)} className="hover:opacity-70">{t.running ? '⏸' : '▶️'}</button>
              ) : (
                <span>🔔</span>
              )}
              <button onClick={() => removeTimer(t.id)} className="hover:opacity-70 text-xs">✕</button>
            </div>
          ))}
        </div>
      )}

      {/* Current Step */}
      <div className="flex-1 flex items-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            className="card p-8 w-full"
          >
            <div className="text-sm text-gray-400 mb-2">Step {step.step_number} of {session.total_steps}</div>
            <p className="text-xl leading-relaxed">{step.instruction}</p>

            {step.duration_minutes && (
              <button
                onClick={() => startTimer(step.step_number, step.timer_label || `Step ${step.step_number}`, step.duration_minutes)}
                className="mt-4 btn-primary flex items-center gap-2"
              >
                ⏱ Start Timer — {step.duration_minutes} min
                {step.timer_label && ` (${step.timer_label})`}
              </button>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between mt-6 pb-4">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="btn-secondary disabled:opacity-30"
        >
          ← Previous
        </button>

        <span className="text-sm text-gray-400">
          {currentStep + 1} / {session.total_steps}
        </span>

        <button onClick={nextStep} className="btn-primary">
          {currentStep === session.steps.length - 1 ? '✅ Done!' : 'Next →'}
        </button>
      </div>
    </div>
  );
}


// ---------- Finished / Rating Screen ----------

function FinishedScreen({ recipeId, recipeName, currentUser, onDone }: {
  recipeId: number;
  recipeName: string;
  currentUser: any;
  onDone: () => void;
}) {
  const [stars, setStars] = useState(5);
  const [wouldMakeAgain, setWouldMakeAgain] = useState(true);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    if (!currentUser) return;
    setSubmitting(true);
    await createRating({
      recipe_id: recipeId,
      user_id: currentUser.id,
      stars,
      would_make_again: wouldMakeAgain,
      notes,
    });
    setSubmitting(false);
    setSubmitted(true);
  };

  return (
    <div className="max-w-md mx-auto text-center space-y-6 py-8">
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} className="text-6xl">
        🎉
      </motion.div>

      <h1 className="text-2xl font-bold">Nice work, Chef!</h1>
      <p className="text-gray-500">{recipeName}</p>

      {!submitted ? (
        <div className="card p-6 text-left">
          <h3 className="font-semibold text-center mb-4">How was it? ({currentUser?.name})</h3>

          <div className="flex justify-center gap-2 text-4xl mb-4">
            {[1, 2, 3, 4, 5].map(s => (
              <button
                key={s}
                onClick={() => setStars(s)}
                className={`transition-transform hover:scale-110 ${s <= stars ? 'text-brand-500' : 'text-gray-300'}`}
              >
                ★
              </button>
            ))}
          </div>

          <label className="flex items-center gap-2 mb-4 justify-center">
            <input type="checkbox" checked={wouldMakeAgain} onChange={(e) => setWouldMakeAgain(e.target.checked)} />
            <span>Would make again 🔄</span>
          </label>

          <textarea
            className="input mb-4"
            placeholder="Any notes? (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
          />

          <div className="flex gap-3">
            <button onClick={onDone} className="btn-secondary flex-1">Skip</button>
            <button onClick={handleSubmit} disabled={submitting} className="btn-primary flex-1">
              {submitting ? 'Saving...' : 'Rate it!'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-green-600 font-medium">Rating saved! ⭐</p>
          <button onClick={onDone} className="btn-primary">Back to Recipe</button>
        </div>
      )}
    </div>
  );
}
