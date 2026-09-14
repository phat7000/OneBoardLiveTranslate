using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Windows.Forms;

// Product/version attributes are generated from branding.py and version.py.
internal static class OneBoardLauncher
{
    private static string Quote(string value)
    {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { slashes++; continue; }
            if (character == '"')
            {
                result.Append('\\', slashes * 2 + 1);
                result.Append(character);
                slashes = 0;
                continue;
            }
            result.Append('\\', slashes);
            slashes = 0;
            result.Append(character);
        }
        result.Append('\\', slashes * 2);
        return result.Append('"').ToString();
    }

    [STAThread]
    private static int Main(string[] arguments)
    {
        string product = ((AssemblyProductAttribute)Attribute.GetCustomAttribute(
            Assembly.GetExecutingAssembly(), typeof(AssemblyProductAttribute))).Product;
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python = Path.Combine(root, "runtime", "python.exe");
            string entry = Path.Combine(root, "app", "oneboard_launch.py");
            if (!File.Exists(python) || !File.Exists(entry))
                throw new FileNotFoundException("Application files are missing. Extract the complete ZIP or reinstall the application.");

            string profile = Environment.GetEnvironmentVariable("ONEBOARD_DATA_DIR");
            if (String.IsNullOrEmpty(profile))
                profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    Assembly.GetExecutingAssembly().GetName().Name);
            if (!Path.IsPathRooted(profile))
                throw new ArgumentException("ONEBOARD_DATA_DIR must be an absolute path.");
            string logFolder = Path.Combine(profile, "logs");
            Directory.CreateDirectory(logFolder);
            string logPath = Path.Combine(logFolder, "launcher.log");
            // Bound startup logs independently of the upstream per-session logs.
            if (File.Exists(logPath) && new FileInfo(logPath).Length > 2 * 1024 * 1024)
            {
                string previous = logPath + ".previous";
                if (File.Exists(previous)) File.Delete(previous);
                File.Move(logPath, previous);
            }
            using (var output = new StreamWriter(new FileStream(logPath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite), Encoding.UTF8))
            using (var process = new Process())
            {
                output.AutoFlush = true;
                process.StartInfo = new ProcessStartInfo(python, "-E -s -B -X utf8 " + Quote(entry));
                foreach (string argument in arguments)
                    process.StartInfo.Arguments += " " + Quote(argument);
                process.StartInfo.WorkingDirectory = root;
                process.StartInfo.UseShellExecute = false;
                process.StartInfo.CreateNoWindow = true;
                process.StartInfo.WindowStyle = ProcessWindowStyle.Hidden;
                process.StartInfo.RedirectStandardOutput = true;
                process.StartInfo.RedirectStandardError = true;
                process.StartInfo.StandardOutputEncoding = Encoding.UTF8;
                process.StartInfo.StandardErrorEncoding = Encoding.UTF8;
                process.StartInfo.EnvironmentVariables["ONEBOARD_DATA_DIR"] = profile;
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) {
                    if (e.Data != null) { lock (output) output.WriteLine(e.Data); }
                };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) {
                    if (e.Data != null) { lock (output) output.WriteLine(e.Data); }
                };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                if (process.ExitCode != 0 && arguments.Length == 0)
                    MessageBox.Show("The application could not start. Details are saved in:\n" + logPath,
                        product, MessageBoxButtons.OK, MessageBoxIcon.Error);
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            if (arguments.Length == 0)
                MessageBox.Show(error.Message, product, MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
