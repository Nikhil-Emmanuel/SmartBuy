import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 px-6 py-32 text-center">
      <span className="font-display text-6xl text-primary">404</span>
      <h1 className="text-xl font-semibold">This page wandered off budget</h1>
      <p className="text-sm text-muted-foreground">
        Nothing here matches your request. Let&apos;s get you back to shopping.
      </p>
      <Button asChild>
        <Link to="/">Back to home</Link>
      </Button>
    </div>
  );
}
