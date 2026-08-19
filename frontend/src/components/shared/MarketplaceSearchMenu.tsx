import { ExternalLink, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { REAL_MARKETPLACES, marketplaceQuery } from "@/lib/productMedia";
import type { Product } from "@/types/api";

/**
 * Sends the user to a *search* on a real marketplace rather than a product
 * page. The catalog is generated, so a SKU here has no listing anywhere; the
 * honest affordance is "go look for this kind of thing", and the copy says so
 * rather than dressing a dead link up as a buy button.
 */
export function MarketplaceSearchMenu({
  product,
  size = "icon-sm",
}: {
  product: Product;
  size?: "icon-sm" | "sm";
}) {
  const query = marketplaceQuery(product);

  return (
    <Popover>
      <PopoverTrigger asChild>
        {size === "sm" ? (
          <Button variant="outline" size="sm" className="h-7 gap-1.5 px-2 text-xs">
            <Search className="size-3.5" /> Find it
          </Button>
        ) : (
          <Button variant="outline" size="icon-sm" title="Search for this on a real marketplace">
            <Search className="size-3.5" />
          </Button>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 p-3">
        <p className="text-xs font-medium text-foreground">Search a real marketplace</p>
        <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
          This listing is simulated demo data, so there&apos;s no real page to open. These
          search for &ldquo;{query}&rdquo; on a live site instead.
        </p>
        <div className="mt-3 flex flex-col gap-1.5">
          {REAL_MARKETPLACES.map((market) => (
            <Button key={market.key} variant="outline" size="sm" className="justify-between" asChild>
              <a href={market.search(query)} target="_blank" rel="noreferrer noopener">
                {market.label}
                <ExternalLink className="size-3.5" />
              </a>
            </Button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
