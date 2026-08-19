import { hashOf } from "@/lib/utils";

/**
 * Photo search terms per catalog subcategory. The catalog is generated, so a
 * product's *name* is synthetic and searches badly ("Voyagr Adventure Pouch
 * Lite" matches nothing); its subcategory is the real signal, so that is what
 * we search on. Terms are deliberately generic — we are illustrating the kind
 * of product, not claiming to show the exact listing.
 */
const SUBCATEGORY_TERMS: Record<string, string> = {
  eyewear: "sunglasses",
  gaiters: "hiking,gaiters",
  gloves: "winter,gloves",
  headwear: "beanie,hat",
  laptop_bag: "laptop,bag",
  neckwear: "scarf",
  umbrella: "umbrella",
  bedsheet: "bedsheet,linen",
  blanket: "blanket",
  mattress: "mattress",
  pillow: "pillow",
  sleeping_bag: "sleeping,bag",
  sleeping_mat: "camping,mat",
  stove: "camping,stove",
  tent: "tent,camping",
  fleece: "fleece,jacket",
  pants: "trousers,outdoor",
  socks: "wool,socks",
  thermals: "thermal,clothing",
  charger: "charger",
  earbuds: "earbuds",
  headphones: "headphones",
  keyboard: "keyboard",
  laptop: "laptop",
  lighting: "lamp,light",
  monitor: "computer,monitor",
  mouse: "computer,mouse",
  power_bank: "power,bank",
  power_strip: "power,strip",
  router: "wifi,router",
  smartwatch: "smartwatch",
  speaker: "speaker",
  storage: "hard,drive",
  webcam: "webcam",
  backpack: "hiking,backpack",
  daypack: "backpack",
  multi_tool: "multitool",
  trekking_poles: "trekking,poles",
  trekking_shoes: "hiking,boots",
  chair: "chair,furniture",
  curtains: "curtains",
  mat: "doormat,rug",
  mirror: "mirror",
  shelving: "shelf,furniture",
  table: "table,furniture",
  bladder: "hydration,pack",
  bottle: "water,bottle",
  flask: "thermos,flask",
  cooker: "pressure,cooker",
  cooktop: "gas,stove,kitchen",
  cookware: "cookware,pan",
  purifier: "water,purifier",
  tableware: "plates,tableware",
  headlamp: "headlamp,torch",
  jacket: "winter,jacket",
  rainwear: "raincoat",
  cleaning: "cleaning,supplies",
  iron: "clothes,iron",
  skincare: "skincare,bottle",
  towel: "towel",
  emergency: "emergency,kit",
  first_aid: "first,aid,kit",
  bathroom: "bathroom,storage",
  dry_bag: "dry,bag",
  hangers: "clothes,hangers",
  laundry: "laundry,basket",
  luggage: "suitcase,luggage",
  rack: "storage,rack",
};

const CATEGORY_FALLBACK_TERMS: Record<string, string> = {
  accessories: "accessories",
  bedding: "bedding",
  camping: "camping,gear",
  clothing: "clothing",
  electronics: "electronics",
  equipment: "outdoor,gear",
  footwear: "shoes",
  furniture: "furniture",
  hydration: "water,bottle",
  kitchen: "kitchenware",
  navigation: "torch,light",
  outerwear: "jacket",
  personal_care: "toiletries",
  safety: "safety,kit",
  storage: "storage,box",
};

/**
 * A real photograph illustrating this kind of product, from LoremFlickr (CC
 * Flickr images, no API key). `lock` is derived from the product id so a given
 * product always renders the same photo — a card that reshuffled its picture on
 * every re-render would look broken during a demo.
 *
 * This is illustrative stock photography, NOT a picture of the actual listing:
 * the catalog is simulated and has no real images. Callers must keep the
 * simulated-data labelling visible alongside it.
 */
export function productPhotoUrl(
  { id, category, subcategory }: { id: string; category: string; subcategory?: string | null },
  size: { w: number; h: number } = { w: 400, h: 300 },
): string {
  const terms =
    (subcategory && SUBCATEGORY_TERMS[subcategory]) ||
    CATEGORY_FALLBACK_TERMS[category] ||
    "product";
  const lock = (hashOf(id) % 100000) + 1;
  return `https://loremflickr.com/${size.w}/${size.h}/${terms}?lock=${lock}`;
}

/**
 * Caps how many product photos are in flight at once.
 *
 * A discovery page renders ~100 cards. Pointing 100 <img> tags at one host makes
 * the browser queue them all behind its ~6-connections-per-host limit, so the
 * first card paints no sooner than the hundredth and the page looks hung for
 * many seconds. Admitting them in small batches in mount order means the cards
 * a user is actually looking at resolve first. `loading="lazy"` does not do this
 * on its own, and IntersectionObserver is not reliable in every host we run in.
 */
const MAX_IN_FLIGHT = 6;
let inFlight = 0;
const waiting: (() => void)[] = [];

export function acquireImageSlot(): Promise<() => void> {
  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    inFlight -= 1;
    waiting.shift()?.();
  };

  if (inFlight < MAX_IN_FLIGHT) {
    inFlight += 1;
    return Promise.resolve(release);
  }
  return new Promise((resolve) => {
    waiting.push(() => {
      inFlight += 1;
      resolve(release);
    });
  });
}

/**
 * Marketplaces the demo catalog's fictional "Marketplace A/B/C" sources do not
 * correspond to. We therefore never deep-link to a product page (there is no
 * real listing behind a generated SKU); we hand the user a *search* on a real
 * marketplace for the product's name, which is a thing they can actually act on.
 */
export const REAL_MARKETPLACES = [
  { key: "amazon", label: "Amazon", search: (q: string) => `https://www.amazon.in/s?k=${encodeURIComponent(q)}` },
  { key: "flipkart", label: "Flipkart", search: (q: string) => `https://www.flipkart.com/search?q=${encodeURIComponent(q)}` },
] as const;

/**
 * Strips the invented brand from a generated product name so the search reads
 * like something a person would type. "Voyagr Adventure First-Aid Pouch Lite"
 * with brand "Voyagr" becomes "Adventure First-Aid Pouch Lite".
 */
export function marketplaceQuery(product: { name: string; brand?: string | null }): string {
  const { name, brand } = product;
  if (brand && name.toLowerCase().startsWith(brand.toLowerCase())) {
    const stripped = name.slice(brand.length).trim();
    if (stripped) return stripped;
  }
  return name;
}
