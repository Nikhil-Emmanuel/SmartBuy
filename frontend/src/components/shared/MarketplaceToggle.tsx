import { Info, Store } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { useMarketplaces } from "@/hooks/useProducts";
import { compactNumber } from "@/lib/format";
import { useAppStore } from "@/store/useAppStore";

/**
 * Chooses which marketplaces feed search, recommendations and bundles.
 *
 * Sources with no credentials configured are listed but disabled, with the
 * reason shown, rather than hidden -- "we did not integrate this and here is
 * why" is more honest than an option that quietly does not exist.
 */
export function MarketplaceToggle() {
  const { data } = useMarketplaces();
  const enabled = useAppStore((s) => s.enabledSources);
  const toggleSource = useAppStore((s) => s.toggleSource);
  const setEnabledSources = useAppStore((s) => s.setEnabledSources);

  const markets = data?.marketplaces ?? [];
  const available = markets.filter((m) => m.available);
  const allKeys = available.map((m) => m.key);
  const active = enabled ?? allKeys;
  const isOn = (key: string) => active.includes(key);
  const noneOn = active.length === 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-1.5" title="Choose marketplaces">
          <Store className="size-4" />
          <span className="hidden sm:inline">Marketplaces</span>
          <Badge variant={noneOn ? "danger" : "secondary"} className="px-1.5 py-0 text-[10px]">
            {active.length}/{available.length}
          </Badge>
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-0">
        <div className="border-b border-border px-4 py-3">
          <p className="text-sm font-medium text-foreground">Marketplaces</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Only the ones switched on are searched, ranked and bundled.
          </p>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {markets.map((market) => (
            <label
              key={market.key}
              className={
                "flex items-start gap-3 rounded-lg px-2 py-2.5 " +
                (market.available ? "cursor-pointer hover:bg-muted/60" : "opacity-60")
              }
            >
              <Switch
                checked={market.available && isOn(market.key)}
                disabled={!market.available}
                onCheckedChange={() => toggleSource(market.key, allKeys)}
                className="mt-0.5"
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-foreground">{market.label}</span>
                  {market.live ? (
                    <Badge variant="savings" className="px-1.5 py-0 text-[10px]">
                      Live
                    </Badge>
                  ) : (
                    <Badge variant="caution" className="px-1.5 py-0 text-[10px]">
                      Simulated
                    </Badge>
                  )}
                </span>
                {market.available ? (
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {compactNumber(market.product_count)} products
                  </span>
                ) : (
                  <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                    {market.note}
                  </span>
                )}
              </span>
            </label>
          ))}
        </div>

        {noneOn && (
          <div className="flex items-start gap-2 border-t border-border bg-danger-soft/40 px-4 py-2.5">
            <Info className="mt-0.5 size-3.5 shrink-0 text-danger" />
            <p className="text-[11px] leading-snug text-danger">
              Every marketplace is off, so nothing can be recommended.
            </p>
          </div>
        )}

        <div className="flex justify-between gap-2 border-t border-border px-3 py-2.5">
          <Button variant="ghost" size="sm" onClick={() => setEnabledSources([])}>
            Clear all
          </Button>
          <Button variant="outline" size="sm" onClick={() => setEnabledSources(null)}>
            Select all
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
