import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import App from "./App";

describe("App", () => {
  it("renders the admin dashboard heading", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", {
        name: /admin workspace for a practical office access-control system/i,
      }),
    ).toBeInTheDocument();
  });
});
