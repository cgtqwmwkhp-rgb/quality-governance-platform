import * as React from 'react'
import { cn } from '../../helpers/utils'

type RadioGroupContextValue = {
  value?: string
  onValueChange?: (value: string) => void
  name: string
}

const RadioGroupContext = React.createContext<RadioGroupContextValue | null>(null)

function useRadioGroupContext() {
  const ctx = React.useContext(RadioGroupContext)
  if (!ctx) {
    throw new Error('RadioGroupItem must be used within RadioGroup')
  }
  return ctx
}

export interface RadioGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: string
  onValueChange?: (value: string) => void
}

const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  ({ className, value, onValueChange, ...props }, ref) => {
    const name = React.useId()
    const contextValue = React.useMemo(
      () => ({ value, onValueChange, name }),
      [value, onValueChange, name],
    )

    return (
      <RadioGroupContext.Provider value={contextValue}>
        <div
          ref={ref}
          role="radiogroup"
          className={cn('grid gap-2', className)}
          {...props}
        />
      </RadioGroupContext.Provider>
    )
  },
)
RadioGroup.displayName = 'RadioGroup'

export interface RadioGroupItemProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'value'> {
  value: string
}

const RadioGroupItem = React.forwardRef<HTMLInputElement, RadioGroupItemProps>(
  ({ className, value, disabled, id, ...props }, ref) => {
    const { value: groupValue, onValueChange, name } = useRadioGroupContext()
    const generatedId = React.useId()
    const inputId = id ?? generatedId

    return (
      <label
        htmlFor={inputId}
        className={cn(
          'inline-flex cursor-pointer items-center gap-2 text-sm font-medium leading-none',
          disabled && 'cursor-not-allowed opacity-50',
          className,
        )}
      >
        <span className="relative flex h-4 w-4 shrink-0 items-center justify-center">
          <input
            ref={ref}
            id={inputId}
            type="radio"
            name={name}
            value={value}
            checked={groupValue === value}
            disabled={disabled}
            onChange={() => onValueChange?.(value)}
            className={cn(
              'peer sr-only',
              'focus-visible:outline-none',
            )}
            {...props}
          />
          <span
            className={cn(
              'pointer-events-none absolute inset-0 flex items-center justify-center rounded-full border border-input bg-background shadow-sm transition-colors',
              'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background',
              'peer-checked:border-primary peer-disabled:opacity-50',
              'peer-checked:[&_[data-radio-dot]]:opacity-100',
            )}
            aria-hidden
          >
            <span
              data-radio-dot
              className="h-2 w-2 rounded-full bg-primary opacity-0 transition-opacity"
            />
          </span>
        </span>
      </label>
    )
  },
)
RadioGroupItem.displayName = 'RadioGroupItem'

export { RadioGroup, RadioGroupItem }
