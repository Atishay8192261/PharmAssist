"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Minus, Plus } from "lucide-react"

interface QuantityInputProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  disabled?: boolean
  debounceMs?: number // deprecated (no longer auto-updates parent)
}

export function QuantityInput({
  value,
  onChange,
  min = 1,
  max = 9999,
  disabled = false,
  debounceMs = 300, // retained for backwards compatibility
}: QuantityInputProps) {
  const [localValue, setLocalValue] = useState(value)
  const lastPropValueRef = useRef(value)

  // Sync local state when parent value changes externally
  useEffect(() => {
    if (value !== lastPropValueRef.current) {
      lastPropValueRef.current = value
      setLocalValue(value)
    }
  }, [value])

  const commitChange = (next: number) => {
    if (next !== value) {
      onChange(next)
    }
  }

  const handleIncrement = () => {
    if (localValue < max && !disabled) {
      const next = localValue + 1
      setLocalValue(next)
      commitChange(next)
    }
  }

  const handleDecrement = () => {
    if (localValue > min && !disabled) {
      const next = localValue - 1
      setLocalValue(next)
      commitChange(next)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return
    const raw = e.target.value
    if (raw === "") {
      setLocalValue(NaN)
      return
    }
    const parsed = Number.parseInt(raw, 10)
    if (!Number.isNaN(parsed)) {
      setLocalValue(parsed)
    }
  }

  const handleBlur = () => {
    let next = localValue
    if (Number.isNaN(next)) next = value // revert invalid empty edit
    if (next < min) next = min
    if (next > max) next = max
    setLocalValue(next)
    commitChange(next)
  }

  return (
    <div className="flex items-center space-x-2">
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8 bg-transparent"
        onClick={handleDecrement}
        disabled={disabled || localValue <= min}
        type="button"
      >
        <Minus className="h-3 w-3" />
        <span className="sr-only">Decrease quantity</span>
      </Button>
      <Input
        type="number"
        value={Number.isNaN(localValue) ? "" : localValue}
        onChange={handleInputChange}
        onBlur={handleBlur}
        className="h-8 w-16 text-center [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
        disabled={disabled}
        min={min}
        max={max}
      />
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8 bg-transparent"
        onClick={handleIncrement}
        disabled={disabled || localValue >= max}
        type="button"
      >
        <Plus className="h-3 w-3" />
        <span className="sr-only">Increase quantity</span>
      </Button>
    </div>
  )
}
