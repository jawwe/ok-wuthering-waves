using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

[assembly: AssemblyTitle("AsterDesk")]
[assembly: AssemblyDescription("Desktop client")]
[assembly: AssemblyCompany("AsterDesk Contributors")]
[assembly: AssemblyProduct("AsterDesk")]
[assembly: AssemblyVersion("1.0.0.0")]
[assembly: AssemblyFileVersion("1.0.0.0")]

internal static class Launcher
{
    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string logs = Path.Combine(root, "data", "logs");
        Directory.CreateDirectory(logs);
        try
        {
            string runtime = Path.Combine(root, "runtime");
            string app = Path.Combine(root, "app");
            bool check = args.Length == 1 && args[0] == "--self-check";
            string entry = Path.Combine(app, check ? "self_check.py" : "main.py");
            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = Path.Combine(runtime, "AsterRuntime.exe");
            info.Arguments = "-s -B \"" + entry + "\"";
            info.WorkingDirectory = app;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            string[] inherited = new string[info.EnvironmentVariables.Count];
            info.EnvironmentVariables.Keys.CopyTo(inherited, 0);
            foreach (string key in inherited)
                if (key.StartsWith("PYAPPIFY_", StringComparison.OrdinalIgnoreCase))
                    info.EnvironmentVariables.Remove(key);
            info.EnvironmentVariables["ASTERDESK_ROOT"] = root;
            info.EnvironmentVariables["PYTHONHOME"] = runtime;
            info.EnvironmentVariables["PYTHONPATH"] = app;
            info.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            if (check) info.EnvironmentVariables["QT_QPA_PLATFORM"] = "offscreen";
            object sync = new object();
            using (StreamWriter output = new StreamWriter(Path.Combine(logs, "launcher.log"), true))
            using (Process worker = new Process())
            {
                output.AutoFlush = true;
                worker.StartInfo = info;
                DataReceivedEventHandler write = delegate(object sender, DataReceivedEventArgs line) {
                    if (line.Data != null) lock (sync) { output.WriteLine(line.Data); }
                };
                worker.OutputDataReceived += write;
                worker.ErrorDataReceived += write;
                worker.Start();
                worker.BeginOutputReadLine();
                worker.BeginErrorReadLine();
                worker.WaitForExit();
                int code = worker.ExitCode;
                if (code != 0 && !check)
                    MessageBox.Show("The client exited with an error. See data/logs/launcher.log.", "AsterDesk");
                return code;
            }
        }
        catch (Exception error)
        {
            File.AppendAllText(Path.Combine(logs, "launcher.log"), error.ToString());
            MessageBox.Show("Unable to start the client. See data/logs/launcher.log.", "AsterDesk");
            return 1;
        }
    }
}
