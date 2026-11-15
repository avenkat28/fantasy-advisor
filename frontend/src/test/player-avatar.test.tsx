import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlayerAvatar } from "@/components/player-avatar";

describe("player photos", () => {
  it("falls back to initials when the free source image fails", () => {
    const player = {player_id: "a", player_name: "Test Runner", team: "BUF", position: "RB", headshot_url: "https://example.com/a.png"};
    const { container, rerender } = render(<PlayerAvatar player={player} />);
    fireEvent.error(container.querySelector("img")!);
    expect(screen.getByText("TR")).toBeInTheDocument();
    rerender(<PlayerAvatar player={{...player, headshot_url: "https://example.com/new.png"}} />);
    expect(container.querySelector("img")).toHaveAttribute("src", "https://example.com/new.png");
  });
});
