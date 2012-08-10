using System;
using System.Collections.Generic;
using System.Linq;
using System.Xml;
using System.Xml.Linq;
using System.IO;
using System.Web;
using Jayrock;
using Jayrock.Json;
using Jayrock.Json.Conversion;

namespace Echonestifier
{
    class Program
    {
        static IEnumerable<XElement> SimpleStreamAxis(string inputUrl, string matchName) 
        {
             using (XmlReader reader = XmlReader.Create(inputUrl)) 
             {
                 reader.MoveToContent();

                 while (reader.Read())
                 { 
                    switch (reader.NodeType)
                    {
                        case XmlNodeType.Element:
                            if (reader.Name == matchName)
                            {
                                XElement el = XElement.ReadFrom(reader) as XElement;

                                if (el != null) {
                                    yield return el;
                                }
                            }
                            break;
                    }
                 }
                 reader.Close();
             }
        }

        static void Main(string[] args)
        {
            if (args.Length != 2)
            {
                Console.WriteLine(@"Usage: Echonestifier C:\Path\To\ExtractFile.xml D:\Path\To\OutputFile.json");
                return;
            }

            string sourceFile = args[0];
            string destinationFile = args[1];

            IEnumerable<string> artistNodes =
                from el in SimpleStreamAxis(sourceFile, "artist")
                select (string)(el.Element("artistId").Value + "|" + el.Element("name").Value);

            var artists = new Dictionary<string, string>();
            int count = 0;

            foreach (string s in artistNodes)
            {
                string[] a = s.Split('|');
                artists.Add(a[0], a[1]);

                Console.Write("\r{0} artists parsed", (++count).ToString());
            }

            IEnumerable<string> trackNodes =
                from el in SimpleStreamAxis(sourceFile, "track")
                where el.Element("artistId") != null
                select (string)(el.Element("trackId").Value + "|" + el.Element("name").Value + "|" + el.Element("isrc").Value + "|" + el.Element("artistId").Value);

            using (StreamWriter outfile = new StreamWriter(destinationFile, false, new System.Text.UTF8Encoding(false)))
            {
                Console.Write("\n");
                count = 0;
                
                foreach (string s in trackNodes)
                {
                    string[] t = s.Split('|');

                    // TODO: Since artists and albums aren't marked for inclusion in incrementals
                    // even when their tracks change, we should instead gather these and query 
                    // content server for their names.

                    if (artists.ContainsKey(t[3]) && t[2].Trim() != "")
                    {
                        var track = new {
                           id = t[0],
                           name = t[1],
                           ISRC = t[2].Replace("tra_isrc.", ""),
                           artist = new {
                               id = t[3],
                               name = artists[t[3]]
                           },
                           type = "track",
                           regions = new string[] { "US" }
                        };

                        outfile.WriteLine(JsonConvert.ExportToString(track));
                    }

                    Console.Write("\r{0} tracks parsed", (++count).ToString());
                }
            }

            Console.Write("\n");
            Console.WriteLine("Done!");
        }
    }
}
