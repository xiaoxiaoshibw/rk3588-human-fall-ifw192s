using System.Text;
using System.Buffers.Binary;

internal static class SelfChecks
{
    internal static object Run()
    {
        byte[] Cloud(bool big,bool bad=false)
        {
            using MemoryStream output=new();using BinaryWriter w=new(output);
            void Text(string s){byte[] b=Encoding.UTF8.GetBytes(s);w.Write(b.Length);w.Write(b);}
            w.Write(7u);w.Write(100u);w.Write(123u);Text("lidar");
            w.Write(3u);w.Write(1u);w.Write(4u);
            for(int i=0;i<4;i++){Text(new[]{"x","y","z","intensity"}[i]);w.Write((uint)i*4);w.Write((byte)7);w.Write(1u);}
            w.Write(big);w.Write(16u);w.Write(bad?8u:20u);w.Write(60u);
            byte[] data=new byte[60];
            for(int row=0;row<3;row++)for(int c=0;c<4;c++)
            {
                float value=row==1 && c==0?float.NaN:row+c+1;
                if(big)BinaryPrimitives.WriteSingleBigEndian(data.AsSpan(row*20+c*4,4),value);
                else BinaryPrimitives.WriteSingleLittleEndian(data.AsSpan(row*20+c*4,4),value);
            }
            w.Write(data);w.Write(false);return output.ToArray();
        }
        CloudFrame little=LiveSource.DecodeCloud(Cloud(false)),big=LiveSource.DecodeCloud(Cloud(true));
        if(!little.RawXyz.SequenceEqual(big.RawXyz) || little.RawXyz.Length!=36 || little.Scene.Length!=24
            || BinaryPrimitives.ReadSingleLittleEndian(little.RawXyz.AsSpan(24,4))!=3
            || BinaryPrimitives.ReadSingleLittleEndian(little.Scene.AsSpan(12,4))!=3
            || little.Intensity is null || big.Intensity is null || !little.Intensity.SequenceEqual(big.Intensity)
            || little.Intensity.Length!=8 || BinaryPrimitives.ReadSingleLittleEndian(little.Intensity.AsSpan(4))!=6
            || little.Key!="7/100/123/lidar")throw new InvalidDataException("ROS endianness/row padding/source-index check failed");
        bool rejected=false;
        try{LiveSource.DecodeCloud(Cloud(false,true));}catch(InvalidDataException){rejected=true;}
        if(!rejected)throw new InvalidDataException("Bad ROS rowStep accepted");
        return new{rosEndian=true,organizedPadding=true,nonfiniteRowsPreserved=true,validRowAfterNaNPreserved=true,badRowStepRejected=true};
    }
}
