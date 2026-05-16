'use client'

import { useCallback } from 'react'
import {
  motion,
  useAnimation,
  useMotionValue,
  useTransform,
  type PanInfo,
} from 'framer-motion'
import type { Poem } from '../types'

interface Props {
  poem: Poem
  preview: string
  onSkip: () => void
  onOpen: () => void
}

const SWIPE_DIST = 80
const SWIPE_VEL = 500
// Drags under this distance are treated as accidental and resolved as taps.
const TAP_THRESHOLD = 10

export function SwipeCard({ poem, preview, onSkip, onOpen }: Props) {
  const controls = useAnimation()
  const x = useMotionValue(0)
  const rotate = useTransform(x, [-160, 160], [-7, 7])
  const skipOpacity = useTransform(x, [-90, -20], [1, 0])

  const handleDragEnd = useCallback(
    async (_: PointerEvent, info: PanInfo) => {
      const { offset, velocity } = info

      if (Math.abs(offset.x) < TAP_THRESHOLD) {
        // Accidental micro-drag — snap back and treat as a tap
        controls.start({ x: 0, transition: { type: 'spring', stiffness: 420, damping: 36 } })
        onOpen()
      } else if (offset.x < -SWIPE_DIST || velocity.x < -SWIPE_VEL) {
        // Left swipe → skip
        await controls.start({
          x: -600,
          opacity: 0,
          transition: { duration: 0.22, ease: 'easeOut' },
        })
        onSkip()
      } else {
        // Right swipe or partial drag → snap back (inert for v1)
        controls.start({ x: 0, transition: { type: 'spring', stiffness: 420, damping: 36 } })
      }
    },
    [controls, onOpen, onSkip],
  )

  return (
    <motion.div
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      dragElastic={1}
      dragMomentum={false}
      onDragEnd={handleDragEnd}
      onTap={onOpen}
      animate={controls}
      style={{ x, rotate, zIndex: 2 }}
      className="absolute inset-0 rounded-2xl bg-[#FAF6E9] shadow-md cursor-grab active:cursor-grabbing flex flex-col px-8 pt-9 pb-8 overflow-hidden"
    >
      {/* Skip hint — fades in as card is dragged left */}
      <motion.span
        style={{ opacity: skipOpacity }}
        className="absolute top-7 right-7 text-[10px] font-sans tracking-[0.18em] text-neutral-300 uppercase pointer-events-none"
      >
        Skip
      </motion.span>

      {/* Title */}
      <p className="font-serif text-[1.125rem] leading-[1.3] font-normal text-[#555] mb-5">
        {poem.title}
      </p>

      {/* Preview */}
      <div className="mt-auto">
        <p className="font-serif text-[1.125rem] leading-[1.85] text-[#111] whitespace-pre-wrap">
          {preview}
        </p>
      </div>
    </motion.div>
  )
}
