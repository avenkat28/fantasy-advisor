"use client";
import { ErrorState } from "@/components/ui";
export default function ErrorPage({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <ErrorState
      error="This page could not be displayed. Try loading it again."
      retry={reset}
    />
  );
}
