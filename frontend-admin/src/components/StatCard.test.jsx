import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import StatCard from "./StatCard";

describe("StatCard", () => {
  it("renders title, value, and hint", () => {
    render(
      <StatCard
        title="Devices"
        value="2"
        hint="Two active edge kiosks"
      />,
    );

    expect(screen.getByText("Devices")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Two active edge kiosks")).toBeInTheDocument();
  });
});
