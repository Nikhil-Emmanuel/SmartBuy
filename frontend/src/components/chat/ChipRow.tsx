import { motion } from "framer-motion";

import { listChild, listParent, SPRING, useReducedMotion } from "@/lib/motion";

export function ChipRow({
  chips,
  onSelect,
  disabled,
}: {
  chips: string[];
  onSelect: (chip: string) => void;
  disabled?: boolean;
}) {
  const reduced = useReducedMotion();
  if (!chips.length) return null;

  return (
    <motion.div
      variants={listParent(chips.length)}
      initial={reduced ? false : "hidden"}
      animate="visible"
      className="flex flex-wrap gap-2 pl-11"
    >
      {chips.map((chip) => (
        <motion.button
          key={chip}
          variants={listChild}
          whileHover={reduced || disabled ? undefined : { y: -2 }}
          whileTap={reduced || disabled ? undefined : { scale: 0.96 }}
          transition={SPRING}
          onClick={() => onSelect(chip)}
          disabled={disabled}
          className="cursor-pointer rounded-full border border-border bg-card px-3.5 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-primary/50 hover:bg-primary-soft hover:text-primary disabled:pointer-events-none disabled:opacity-50"
        >
          {chip}
        </motion.button>
      ))}
    </motion.div>
  );
}
