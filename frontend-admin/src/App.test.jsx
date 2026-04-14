import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import App from "./App";

describe("App", () => {
  it("renders the admin dashboard heading and core cards", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /admin workspace for a practical office access-control system/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Employees")).toBeInTheDocument();
    expect(screen.getByText("Gates")).toBeInTheDocument();
    expect(screen.getByText("Queue")).toBeInTheDocument();
  });
});
