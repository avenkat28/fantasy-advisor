"use client";
import { useState } from "react";
import type { Player } from "@/lib/types";

export function PlayerAvatar({ player, large = false }: { player: Player; large?: boolean }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const url = player.headshot_url;
  const initials = player.player_name.split(/[ .]+/).filter(Boolean).map(n => n[0]).slice(0, 2).join("");
  return <span className={`player-avatar${large ? " player-avatar-large" : ""}`} aria-hidden="true">
    {url && url !== failedUrl ? (
      // Public source photos load directly; missing images fall back to initials.
      // eslint-disable-next-line @next/next/no-img-element
      <img src={url} alt="" loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={() => setFailedUrl(url)} />
    ) : initials}
  </span>;
}
