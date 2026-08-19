export function ChipRow({
  chips,
  onSelect,
  disabled,
}: {
  chips: string[];
  onSelect: (chip: string) => void;
  disabled?: boolean;
}) {
  if (!chips.length) return null;

  return (
    <div className="flex flex-wrap gap-2 pl-11">
      {chips.map((chip) => (
        <button
          key={chip}
          onClick={() => onSelect(chip)}
          disabled={disabled}
          className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-primary/50 hover:bg-primary-soft hover:text-primary disabled:pointer-events-none disabled:opacity-50"
        >
          {chip}
        </button>
      ))}
    </div>
  );
}
