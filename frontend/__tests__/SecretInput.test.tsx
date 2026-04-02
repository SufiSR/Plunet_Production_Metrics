import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { SecretInput } from "@/app/components/admin/SecretInput";

describe("SecretInput", () => {
  it("renders as password type by default", () => {
    render(
      <SecretInput
        id="test-token"
        label="Token"
        hint="abc***xyz"
        onChange={() => {}}
      />
    );
    const input = document.getElementById("test-token") as HTMLInputElement;
    expect(input.type).toBe("password");
  });

  it("toggles visibility when button is clicked", () => {
    render(
      <SecretInput
        id="toggle-token"
        label="Token"
        hint={null}
        onChange={() => {}}
      />
    );
    const input = document.getElementById("toggle-token") as HTMLInputElement;
    expect(input.type).toBe("password");

    fireEvent.click(screen.getByRole("button", { name: /show token/i }));
    expect(input.type).toBe("text");

    fireEvent.click(screen.getByRole("button", { name: /hide token/i }));
    expect(input.type).toBe("password");
  });

  it("calls onChange with the typed value", () => {
    const onChange = jest.fn();
    render(
      <SecretInput
        id="value-token"
        label="Token"
        hint={null}
        onChange={onChange}
      />
    );
    const input = document.getElementById("value-token") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "new-secret" } });
    expect(onChange).toHaveBeenCalledWith("new-secret");
  });

  it("calls onChange with empty string when cleared", () => {
    const onChange = jest.fn();
    render(
      <SecretInput
        id="clear-token"
        label="Token"
        hint="abc***"
        onChange={onChange}
      />
    );
    const input = document.getElementById("clear-token") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "typed" } });
    fireEvent.change(input, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith("");
  });

  it("shows hint in placeholder when hint is provided", () => {
    render(
      <SecretInput
        id="hint-token"
        label="Token"
        hint="abc***xyz"
        onChange={() => {}}
      />
    );
    const input = document.getElementById("hint-token") as HTMLInputElement;
    expect(input.placeholder).toContain("abc***xyz");
  });
});
