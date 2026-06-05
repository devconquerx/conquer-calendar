import { useState, useEffect, useRef } from 'react'

export default function StepTransition({ stepKey, direction, children }) {
  const [display, setDisplay] = useState(children)
  const [animClass, setAnimClass] = useState('translate-x-0 opacity-100')
  const isFirstRender = useRef(true)
  const prevStepKey = useRef(stepKey)

  // Always show latest children when stepKey hasn't changed (e.g. error updates)
  useEffect(() => {
    if (prevStepKey.current === stepKey) {
      setDisplay(children)
    }
  }, [children, stepKey])

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      prevStepKey.current = stepKey
      return
    }

    // Slide out current content
    const exitClass = direction === 'forward'
      ? '-translate-x-full opacity-0'
      : 'translate-x-full opacity-0'
    setAnimClass(exitClass)

    const timer1 = setTimeout(() => {
      setDisplay(children)
      prevStepKey.current = stepKey
      // Position new content offscreen on the opposite side
      const enterFrom = direction === 'forward'
        ? 'translate-x-full opacity-0'
        : '-translate-x-full opacity-0'
      setAnimClass(enterFrom)

      // Then slide it in
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setAnimClass('translate-x-0 opacity-100')
        })
      })
    }, 250)

    return () => clearTimeout(timer1)
  }, [stepKey])

  return (
    <div
      className={`transform transition-all duration-300 ease-out ${animClass}`}
    >
      {display}
    </div>
  )
}
