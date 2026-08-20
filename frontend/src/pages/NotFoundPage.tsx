import { motion } from "framer-motion";
import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { EASE_OUT, SPRING, useReducedMotion } from "@/lib/motion";

export function NotFoundPage() {
  const reduced = useReducedMotion();

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 px-6 py-32 text-center">
      <motion.div
        initial={reduced ? false : { scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={SPRING}
        className="relative"
      >
        {/* A compass that can't settle -- the only joke on the page, and it
            stops entirely under reduced motion. */}
        <motion.span
          className="absolute -right-7 top-2 text-primary/60"
          animate={reduced ? {} : { rotate: [0, 160, -40, 220, 0] }}
          transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }}
        >
          <Compass className="size-6" />
        </motion.span>
        <span className="font-display text-6xl text-primary">404</span>
      </motion.div>

      <motion.h1
        initial={reduced ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: reduced ? 0 : 0.1, duration: 0.4, ease: EASE_OUT }}
        className="text-xl font-semibold"
      >
        This page wandered off budget
      </motion.h1>

      <motion.p
        initial={reduced ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: reduced ? 0 : 0.17, duration: 0.4, ease: EASE_OUT }}
        className="text-sm text-muted-foreground"
      >
        Nothing here matches your request. Let&apos;s get you back to shopping.
      </motion.p>

      <motion.div
        initial={reduced ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: reduced ? 0 : 0.24, duration: 0.4, ease: EASE_OUT }}
      >
        <Button asChild>
          <Link to="/">Back to home</Link>
        </Button>
      </motion.div>
    </div>
  );
}
