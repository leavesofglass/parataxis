'use client'

import { motion } from 'framer-motion'
import type { TargetAndTransition } from 'framer-motion'
import type { Poem } from '../types'
import { FullPoemView } from './FullPoemView'
import type { Reactions } from './FullPoemView'

// Non-draggable card wrapper. Drives entry and exit animations via the animate
// prop. Entry animation fires only on Back (enterDir='right'); normal forward
// navigation uses initial=false (instant appear). Exit fires when isExiting is
// true (Next only). onExited is guarded by isExiting so it only fires on actual
// exit, not on completion of a Back entry animation.
export function PoemCard({
  poem,
  activeReactions,
  onReaction,
  onNext,
  onShare,
  isExiting,
  onExited,
  canBack,
  onBack,
}: {
  poem: Poem
  activeReactions: Reactions
  onReaction: (action: 'like' | 'dislike' | 'save') => void
  onNext: () => void
  onShare: () => void
  isExiting: boolean
  onExited: () => void
  canBack: boolean
  onBack: () => void
}) {
  const exitTarget: TargetAndTransition = isExiting
    ? { x: '160%', opacity: 0 }
    : { x: 0, y: 0, opacity: 1 }

  return (
    <motion.div
      className="absolute inset-0"
      style={{ zIndex: 2 }}
      initial={false}
      animate={exitTarget}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      onAnimationComplete={() => { if (isExiting) onExited() }}
    >
      <FullPoemView
        poem={poem}
        activeReactions={activeReactions}
        onReaction={onReaction}
        onNext={onNext}
        onShare={onShare}
        onClose={() => {}}
        asCard
        canBack={canBack}
        onBack={onBack}
      />
    </motion.div>
  )
}
