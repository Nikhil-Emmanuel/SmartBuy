/**
 * The scroll-velocity wave: a 3D row of real catalog products that bends with
 * how hard you scroll.
 *
 * Every tile is a real product from `/api/products/search`, not a placeholder.
 * A landing-page showcase full of invented products would be the exact thing
 * the rest of this repo refuses to do.
 *
 * Each tile is its own component because each one needs its own
 * `useTransform` -- hooks can't run in a loop inside the parent.
 */

import { motion, useReducedMotion, type MotionValue } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { ProductImage } from "@/components/shared/ProductImage";
import { useProductSearch } from "@/hooks/useProducts";
import { rupees } from "@/lib/format";
import {
  useScrollVelocityFactor,
  useVelocityOffset,
  useVelocityTilt,
} from "@/lib/scrollVelocity";
import { cn } from "@/lib/utils";
import type { Product } from "@/types/api";

const TILES = 7;

export function VelocityShowcase() {
  const reduced = useReducedMotion();
  const navigate = useNavigate();
  const factor = useScrollVelocityFactor();
  const { data } = useProductSearch({ sort: "rating", page_size: TILES });
  const products = data?.items?.slice(0, TILES) ?? [];

  if (products.length === 0) return null;

  return (
    <section className="relative py-16">
      <div className="mx-auto mb-8 max-w-2xl px-6 text-center">
        <h2 className="font-display text-2xl text-foreground sm:text-3xl">
          Real products, ranked on eight signals
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Scroll and the row responds to how fast you move — everything below is a live row
          from the catalog.
        </p>
      </div>

      {/*
        `perspective` has to live on the parent for child rotations to read as
        depth rather than as a flat squash. Overflow is hidden because the wave
        deliberately pushes tiles past the edges.
      */}
      <div
        className="flex items-center justify-center gap-3 overflow-hidden px-6 py-12 sm:gap-5"
        style={{ perspective: 1200 }}
      >
        {products.map((product, i) => (
          <VelocityTile
            key={product.id}
            product={product}
            // Seven tiles need roughly 1300px. Narrower screens drop the
            // outer ones rather than pushing them somewhere unreachable --
            // a clipped row you cannot scroll is just hidden content.
            className={
              i >= 3 ? (i >= 5 ? "hidden lg:block" : "hidden sm:block") : undefined
            }
            factor={factor}
            // Spread the row across roughly half a sine period so the middle
            // tiles lead and the ends trail -- that lag is what reads as a wave.
            phase={(i / Math.max(products.length - 1, 1)) * Math.PI}
            reduced={!!reduced}
            onPick={() =>
              navigate("/chat", {
                state: {
                  initialMessage: `Show me ${(product.subcategory || product.category).replace(/_/g, " ")}`,
                },
              })
            }
          />
        ))}
      </div>
    </section>
  );
}

function VelocityTile({
  product,
  factor,
  phase,
  reduced,
  className,
  onPick,
}: {
  product: Product;
  factor: MotionValue<number>;
  phase: number;
  reduced: boolean;
  className?: string;
  onPick: () => void;
}) {
  const y = useVelocityOffset(factor, phase);
  const rotateY = useVelocityTilt(factor, phase);

  return (
    <motion.div
      style={reduced ? undefined : { y, rotateY, transformStyle: "preserve-3d" }}
      whileHover={reduced ? undefined : { scale: 1.06, zIndex: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 24 }}
      className={cn("w-[128px] shrink-0 sm:w-[168px]", className)}
    >
      <button
        type="button"
        onClick={onPick}
        className="block w-full overflow-hidden rounded-xl border border-border bg-card text-left shadow-sm transition-colors hover:border-primary/50"
      >
        <ProductImage
          category={product.category}
          subcategory={product.subcategory}
          seed={product.id}
          className="aspect-[4/3] w-full"
        />
        <div className="p-2.5">
          <p className="line-clamp-2 text-xs leading-snug text-foreground">{product.name}</p>
          <p className="tabular mt-1 text-xs font-semibold text-foreground">
            {rupees(product.price)}
          </p>
        </div>
      </button>
    </motion.div>
  );
}
