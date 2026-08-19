import {
  Armchair,
  Bed,
  Cloud,
  Compass,
  Cpu,
  Footprints,
  GlassWater,
  type LucideIcon,
  Package,
  Shirt,
  ShieldCheck,
  Soup,
  Sparkles,
  Tent,
  Watch,
  Wrench,
} from "lucide-react";

import { cn, hueFrom } from "@/lib/utils";

/**
 * The catalog is generated, not scraped, so no product has a real photo.
 * Rather than fake one, every card gets a deterministic category glyph on a
 * tinted field -- recognisable at a glance and honest about what it is.
 */
const CATEGORY_ICONS: Record<string, LucideIcon> = {
  accessories: Watch,
  bedding: Bed,
  camping: Tent,
  clothing: Shirt,
  electronics: Cpu,
  equipment: Wrench,
  footwear: Footprints,
  furniture: Armchair,
  hydration: GlassWater,
  kitchen: Soup,
  navigation: Compass,
  outerwear: Cloud,
  personal_care: Sparkles,
  safety: ShieldCheck,
  storage: Package,
};

export function ProductImage({
  category,
  seed,
  className,
  iconClassName,
}: {
  category: string;
  seed: string;
  className?: string;
  iconClassName?: string;
}) {
  const Icon = CATEGORY_ICONS[category] ?? Package;
  const hue = hueFrom(seed);

  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-lg",
        className,
      )}
      style={{
        background: `linear-gradient(135deg, hsl(${hue} 70% 94%), hsl(${(hue + 40) % 360} 70% 88%))`,
      }}
    >
      <div
        className="absolute inset-0 opacity-40 dark:opacity-25"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
          backgroundSize: "14px 14px",
          color: `hsl(${hue} 60% 60%)`,
        }}
      />
      <Icon
        className={cn("relative size-8 opacity-80 dark:opacity-90", iconClassName)}
        style={{ color: `hsl(${hue} 45% 32%)` }}
        strokeWidth={1.5}
      />
    </div>
  );
}
