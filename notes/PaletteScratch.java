package com.customnpcmodels.authoring;

import com.customnpcmodels.inject.Mesh;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import javax.imageio.ImageIO;

/** Scratch: derive crab recolors from each spider's palette, and render crab beside spider. */
public class PaletteScratch
{
	static final int[] FIND = {960, -31808, 22443, 11200, -9280, -15437};

	static Mesh load(String path) throws Exception
	{
		return GltfToMeshConverter.convert(Files.readAllBytes(Paths.get(path)), 1_000_001, 1_000_001, new LinkedHashMap<>()).mesh;
	}

	static Map<Integer, Integer> map(int[] find, int[] replace)
	{
		Map<Integer, Integer> m = new HashMap<>();
		for (int i = 0; replace != null && i < find.length; i++)
		{
			m.put(find[i] & 0xFFFF, replace[i] & 0xFFFF);
		}
		return m;
	}

	static int apply(Map<Integer, Integer> m, int c)
	{
		return m.getOrDefault(c & 0xFFFF, c & 0xFFFF);
	}

	/** Colors by face count, most used first, black left out. */
	static List<int[]> palette(Mesh mesh, Map<Integer, Integer> m)
	{
		Map<Integer, Integer> counts = new HashMap<>();
		for (short c : mesh.getFaceColors())
		{
			int color = apply(m, c);
			if (color != 0)
			{
				counts.merge(color, 1, Integer::sum);
			}
		}
		List<int[]> out = new ArrayList<>();
		counts.forEach((k, v) -> out.add(new int[]{k, v}));
		out.sort((a, b) -> b[1] - a[1]);
		return out;
	}

	static double meanL(List<int[]> p, int n)
	{
		double sum = 0, count = 0;
		for (int i = 0; i < n; i++)
		{
			sum += (p.get(i)[0] & 127) * p.get(i)[1];
			count += p.get(i)[1];
		}
		return sum / count;
	}

	static BufferedImage render(Mesh mesh, Map<Integer, Integer> m, int size)
	{
		ModelViewport v = new ModelViewport(mesh, 0, 0)
		{
			@Override
			protected short faceColor(int face)
			{
				return (short) apply(m, mesh.getFaceColors()[face]);
			}
		};
		v.relight();
		v.frame();
		return v.render(size, size);
	}

	public static void main(String[] args) throws Exception
	{
		String dir = args[0];
		Mesh crab = load(dir + "/export/4822/crab.glb");
		List<int[]> crabPalette = palette(crab, Collections.emptyMap());
		int n = 4;
		double crabL = meanL(crabPalette, n);

		Object[][] targets = {
			{"giant 3017/3018", "3017/giant-spider.glb", new int[]{8088, 9098, 8076, 10159, 7700, 7106}},
			{"giant 2477", "3017/giant-spider.glb", new int[]{3992, 5002, 908, 4015, 532, 3010}},
			{"temple 8703", "8703/temple-spider.glb", new int[]{-1122, 916, -7637, 4888, -3785, -22266}},
			{"deadly red 3021", "8703/temple-spider.glb", new int[]{699, -1122, 803, 4888, -22260, -22266}},
			{"sarachnis 8713", "8713/sarachnis.glb", null},
			{"spawn melee 8714", "8714/spawn-of-sarachnis.glb", null, new int[]{906, 910}},
			{"spawn mage 8715", "8715/spawn-of-sarachnis.glb", null, new int[]{906, 910}},
			{"jungle 3020/6267/6271", "3020/jungle-spider.glb", new int[]{16945, 8483, 22823, 22823, 16937}, new int[0], new int[]{-31808, -9280, 22443, -15437, 960}},
		};

		int size = 260;
		BufferedImage sheet = new BufferedImage(size * 2, size * targets.length, BufferedImage.TYPE_INT_RGB);
		Graphics2D g = sheet.createGraphics();
		for (int t = 0; t < targets.length; t++)
		{
			Mesh spider = load(dir + "/export/" + targets[t][1]);
			Map<Integer, Integer> spiderMap = map(targets[t].length > 4 ? (int[]) targets[t][4] : FIND, (int[]) targets[t][2]);
			List<int[]> all = palette(spider, spiderMap);
			Set<Integer> shared = new HashSet<>();
			if (targets[t].length > 3) for (int c : (int[]) targets[t][3]) shared.add(c);
			List<int[]> p = new ArrayList<>();
			for (int[] c : all) if (c[1] >= 10 && !shared.contains(c[0])) p.add(c);
			while (p.size() < n) p.add(p.get(p.size() % Math.max(1, p.size())));
			double ratio = meanL(p, n) / crabL;

			Map<Integer, Integer> crabMap = new LinkedHashMap<>();
			StringBuilder json = new StringBuilder();
			for (int i = 0; i < n; i++)
			{
				int from = crabPalette.get(i)[0];
				int to = p.get(i)[0];
				double scaled = (from & 127) * ratio;
				int toL = to & 127;
				// A spider color darker than the crab's scaled one pulls it down, halfway on a log scale, so near-blacks stay dark
				int l = (int) Math.max(2, Math.min(126, Math.round(toL < scaled ? Math.sqrt(scaled * Math.max(toL, 1)) : scaled)));
				int color = (to & ~127) | l;
				crabMap.put(from, color);
				json.append(i == 0 ? "" : ", ").append("{\"find\": ").append(from).append(", \"replace\": ").append(color).append("}");
			}
			System.out.println(targets[t][0] + ": \"recolors\": [" + json + "]");

			g.drawImage(render(crab, crabMap, size), 0, t * size, null);
			g.drawImage(render(spider, spiderMap, size), size, t * size, null);
			g.setColor(Color.WHITE);
			g.drawString((String) targets[t][0], 6, t * size + 14);
		}
		ImageIO.write(sheet, "png", new File(dir + "/palette/sheet.png"));
	}
}
