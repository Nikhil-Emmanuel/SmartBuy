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
import { useEffect, useState } from "react";

import { acquireImageSlot, productPhotoUrl } from "@/lib/productMedia";
import { cn, hueFrom } from "@/lib/utils";

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

/**
 * Loads the photo off-DOM through a shared concurrency gate, then swaps it in
 * once decoded. Going through `new Image()` rather than rendering an <img> and
 * hoping means the queue actually controls when the request starts.
 */
function useProductPhoto(url: string, enabled: boolean) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let release: (() => void) | undefined;

    acquireImageSlot().then((done) => {
      release = done;
      if (cancelled) return done();
      const img = new Image();
      img.onload = () => {
        if (!cancelled) setSrc(url);
        done();
      };
      img.onerror = () => done();
      img.src = url;
    });

    return () => {
      cancelled = true;
      release?.();
    };
  }, [url, enabled]);

  return src;
}

/**
 * Shows an illustrative stock photo of this *kind* of product, over a
 * deterministic category-glyph field that doubles as the loading state and the
 * offline fallback -- the demo must still look right with no network.
 *
 * The photo is generic stock, not the actual listing: the catalog is generated
 * and has no real images. Cards pair this with the simulated-data badge so the
 * photo is never read as evidence that the price or listing is real.
 */
export function ProductImage({
  category,
  subcategory,
  seed,
  className,
  iconClassName,
  photo = true,
}: {
  category: string;
  subcategory?: string | null;
  seed: string;
  className?: string;
  iconClassName?: string;
  photo?: boolean;
}) {
  const Icon = CATEGORY_ICONS[category] ?? Package;
  const hue = hueFrom(seed);
  const src = useProductPhoto(
    productPhotoUrl({ id: seed, category, subcategory }),
    photo,
  );

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

      {src && (
        <img src={src} alt="" decoding="async" className="absolute inset-0 size-full object-cover" />
      )}
    </div>
  );
}
