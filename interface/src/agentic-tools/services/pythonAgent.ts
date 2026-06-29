import { spawn } from "child_process";
import type { AgentResponse, Location } from "../../retrieval/types";

export function callPythonAgent(
  message: string,
  locations: Location[],
): Promise<AgentResponse> {
  return new Promise((resolve, reject) => {
    const proc = spawn("python", [
      "agent.py",
      JSON.stringify({ message, locations }),
    ]);

    let output = "";
    let error = "";

    proc.stdout.on("data", (d) => (output += d.toString()));
    proc.stderr.on("data", (d) => (error += d.toString()));

    proc.on("close", () => {
      if (error) return reject(error);

      try {
        resolve(JSON.parse(output));
      } catch {
        reject("Bad Python output: " + output);
      }
    });
  });
}